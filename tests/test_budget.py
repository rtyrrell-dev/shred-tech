"""The shared daily request budget: config math, the atomic conditional increment, Pacific-date keys."""

import asyncio
from datetime import datetime, timezone

import pytest
from fakeredis import FakeAsyncRedis

from guards.budget import KEY_GRACE_SECONDS, BudgetExhausted, RequestBudget
from guards.quota import DEFAULT_DAILY_QUOTA, DEFAULT_QUOTA_SAFETY, daily_request_budget, quota_safety
from guards.ratelimit import INCR_IF_BELOW_LUA, GuardUnavailable, MemoryStore, UpstashStore


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


# --- config: GEMINI_DAILY_QUOTA x GEMINI_QUOTA_SAFETY ------------------------

def test_default_budget_is_18_requests():
    assert DEFAULT_DAILY_QUOTA == 20
    assert daily_request_budget() == 18  # floor(20 x 0.9)


@pytest.mark.parametrize(
    "quota, safety, budget",
    [
        (20, "0.9", 18),
        (20, "1", 20),
        (20, "0.5", 10),
        (20, "0.85", 17),
        (15, "0.9", 13),     # 13.5 floors to 13
        (100, "0.9", 90),
        (100, "0.57", 57),   # a float would give 56.99999999999999 and floor it to 56
        (100, "9/10", 90),
    ],
)
def test_budget_is_floor_of_quota_times_safety(monkeypatch, quota, safety, budget):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", str(quota))
    monkeypatch.setenv("GEMINI_QUOTA_SAFETY", safety)
    assert daily_request_budget() == budget


@pytest.mark.parametrize("bad", ["abc", "0", "-0.5", "1.5", "2", "nan", "1/0", "  ", ""])
def test_invalid_safety_falls_back_to_the_default(monkeypatch, bad):
    monkeypatch.setenv("GEMINI_QUOTA_SAFETY", bad)
    assert quota_safety() == DEFAULT_QUOTA_SAFETY
    assert daily_request_budget() == 18


def test_tiny_quota_still_leaves_one_request(monkeypatch):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", "1")
    assert daily_request_budget() == 1


def test_global_daily_limit_variable_is_gone(monkeypatch):
    # The old turn-based override no longer exists and must not affect the request budget.
    monkeypatch.setenv("GLOBAL_DAILY_LIMIT", "999")
    assert daily_request_budget() == 18


# --- the atomic conditional increment (in-memory store) -----------------------

async def test_memory_store_stops_at_the_limit_and_rejections_do_not_inflate():
    store = MemoryStore()
    assert [await store.incr_if_below("k", 3, 60) for _ in range(3)] == [1, 2, 3]
    for _ in range(50):
        assert await store.incr_if_below("k", 3, 60) is None
    assert await store.get_count("k") == 3  # 50 rejected calls changed nothing


async def test_memory_store_counter_expires_after_its_ttl():
    clock = Clock(1000.0)
    store = MemoryStore(clock)
    await store.incr_if_below("k", 3, 60)
    clock.now += 61
    assert await store.get_count("k") == 0


# --- RequestBudget ------------------------------------------------------------

async def test_budget_admits_exactly_the_cap_then_refuses():
    budget = RequestBudget(MemoryStore(), cap=18)
    for expected in range(1, 19):
        assert await budget.take() == expected
    for _ in range(40):
        with pytest.raises(BudgetExhausted):
            await budget.take()
    assert await budget.used() == 18  # never inflated by the 40 rejected attempts


async def test_concurrent_calls_at_the_cap_admit_exactly_the_cap():
    budget = RequestBudget(MemoryStore(), cap=18)
    results = await asyncio.gather(*[budget.take() for _ in range(100)], return_exceptions=True)
    admitted = [r for r in results if isinstance(r, int)]
    refused = [r for r in results if isinstance(r, BudgetExhausted)]
    assert sorted(admitted) == list(range(1, 19))  # 1..18, each handed out exactly once
    assert len(refused) == 82
    assert await budget.used() == 18


async def test_require_available_does_not_spend_anything():
    budget = RequestBudget(MemoryStore(), cap=2)
    await budget.require_available()
    await budget.require_available()
    assert await budget.used() == 0
    await budget.take()
    await budget.take()
    with pytest.raises(BudgetExhausted):
        await budget.require_available()


async def test_exhausted_error_carries_seconds_until_the_pacific_reset():
    clock = Clock(utc(2026, 10, 29, 6, 59, 0))  # one minute before Pacific midnight (07:00 UTC)
    budget = RequestBudget(MemoryStore(clock), cap=1, clock=clock)
    await budget.take()
    with pytest.raises(BudgetExhausted) as exc:
        await budget.take()
    assert exc.value.retry_after == 60


# --- Pacific-date key and TTL -------------------------------------------------

async def test_counter_is_keyed_by_pacific_date_and_resets_at_pacific_midnight():
    clock = Clock(utc(2026, 10, 29, 6, 59, 59))  # still 28 Oct in Pacific time
    store = MemoryStore(clock)
    budget = RequestBudget(store, cap=1, clock=clock)
    await budget.take()
    assert await store.get_count("budget:2026-10-28") == 1
    with pytest.raises(BudgetExhausted):
        await budget.take()

    clock.now = utc(2026, 10, 29, 7, 0, 0)  # Pacific midnight: a new date, a fresh counter
    await budget.take()
    assert await store.get_count("budget:2026-10-29") == 1
    assert await store.get_count("budget:2026-10-28") == 1  # yesterday's key is untouched


async def test_utc_midnight_does_not_reset_the_budget():
    clock = Clock(utc(2026, 10, 28, 23, 59, 59))
    budget = RequestBudget(MemoryStore(clock), cap=1, clock=clock)
    await budget.take()
    clock.now = utc(2026, 10, 29, 0, 0, 1)  # UTC midnight passed; Pacific time is still 28 Oct
    with pytest.raises(BudgetExhausted):
        await budget.take()


async def test_counter_key_expires_shortly_after_the_reset():
    clock = Clock(utc(2026, 10, 29, 6, 0, 0))  # 1 hour before the 07:00 UTC reset
    store = MemoryStore(clock)
    await RequestBudget(store, cap=5, clock=clock).take()
    key = "budget:2026-10-28"
    assert await store.exists(key)
    clock.now = utc(2026, 10, 29, 7, 0, 0) + KEY_GRACE_SECONDS - 1  # just inside the grace period
    assert await store.exists(key)
    clock.now = utc(2026, 10, 29, 7, 0, 0) + KEY_GRACE_SECONDS + 1  # just after it
    assert not await store.exists(key)


async def test_store_outage_fails_closed():
    class Down(MemoryStore):
        async def incr_if_below(self, key, limit, ttl):
            raise ConnectionError("redis down")

        async def get_count(self, key):
            raise ConnectionError("redis down")

    budget = RequestBudget(Down(), cap=18)
    with pytest.raises(GuardUnavailable):
        await budget.take()
    with pytest.raises(GuardUnavailable):
        await budget.require_available()


# --- UpstashStore adapter (fake client) ---------------------------------------

class FakeUpstash:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def eval(self, script, keys=None, args=None):
        self.calls.append((script, keys, args))
        return self.reply

    async def get(self, key):
        return self.reply


async def test_upstash_store_sends_the_script_key_limit_and_ttl():
    fake = FakeUpstash(reply=7)
    assert await UpstashStore(fake).incr_if_below("budget:2026-10-29", 18, 90000) == 7
    assert fake.calls == [(INCR_IF_BELOW_LUA, ["budget:2026-10-29"], ["18", "90000"])]


async def test_upstash_store_maps_the_rejection_code_to_none():
    assert await UpstashStore(FakeUpstash(reply=-1)).incr_if_below("k", 18, 60) is None


async def test_upstash_get_count_handles_missing_and_string_values():
    assert await UpstashStore(FakeUpstash(reply=None)).get_count("k") == 0
    assert await UpstashStore(FakeUpstash(reply="12")).get_count("k") == 12


# --- the real Lua script, run by a Lua engine ----------------------------------
# fakeredis executes the exact script text we send to Upstash (via the lupa Lua runtime), so this
# checks the script's own logic: atomic check-and-increment, rejection leaves the counter alone,
# and the TTL is set once, when the key is created.

@pytest.fixture
async def redis():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


async def run_script(redis, key, limit, ttl):
    return await redis.eval(INCR_IF_BELOW_LUA, 1, key, limit, ttl)


async def test_lua_counts_up_to_the_limit_then_returns_minus_one(redis):
    assert [await run_script(redis, "b", 3, 100) for _ in range(5)] == [1, 2, 3, -1, -1]
    assert await redis.get("b") == "3"  # the two rejected calls did not inflate it


async def test_lua_sets_the_ttl_only_when_the_key_is_created(redis):
    await run_script(redis, "b", 5, 100)
    first_ttl = await redis.ttl("b")
    assert 0 < first_ttl <= 100
    await redis.expire("b", 7)  # shorten it; later increments must not reset it
    await run_script(redis, "b", 5, 100)
    assert 0 < await redis.ttl("b") <= 7


async def test_lua_concurrent_calls_admit_exactly_the_limit(redis):
    results = await asyncio.gather(*[run_script(redis, "b", 18, 100) for _ in range(100)])
    assert sorted(r for r in results if r > 0) == list(range(1, 19))
    assert results.count(-1) == 82
    assert await redis.get("b") == "18"


async def test_lua_treats_a_missing_key_as_zero(redis):
    assert await run_script(redis, "fresh", 1, 60) == 1
    assert await run_script(redis, "fresh", 1, 60) == -1
