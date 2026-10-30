import pytest

from guards import quota
from guards.quota import MAX_CALLS_PER_TURN, daily_quota, global_daily_turn_limit
from guards.ratelimit import Guard, LimitExceeded, MemoryStore


def test_default_quota_is_20_requests_per_day():
    assert daily_quota() == 20


def test_default_global_limit_is_4_turns():
    # floor(20 * 0.8 / 4) = floor(4.0) = 4
    assert global_daily_turn_limit() == 4


@pytest.mark.parametrize(
    "quota_value, turns",
    [
        (20, 4),   # 16 / 4
        (21, 4),   # 16.8 / 4 = 4.2 -> floor 4
        (25, 5),   # 20 / 4
        (35, 7),   # 28 / 4 (a float 0.8*35 would be exactly 28.0, but 0.8*3 would not be exact)
        (100, 20),
        (1500, 300),
    ],
)
def test_global_limit_is_floor_of_80_percent_over_max_calls(monkeypatch, quota_value, turns):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", str(quota_value))
    assert global_daily_turn_limit() == turns
    assert turns == quota_value * 8 // (10 * MAX_CALLS_PER_TURN)


@pytest.mark.parametrize("quota_value", [20, 33, 100, 250, 999])
def test_serving_the_limit_never_exceeds_80_percent_of_the_quota(monkeypatch, quota_value):
    # The point of the formula: even if every turn used the maximum number of requests.
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", str(quota_value))
    assert global_daily_turn_limit() * MAX_CALLS_PER_TURN <= quota_value * 0.8


def test_tiny_quota_still_serves_one_turn(monkeypatch):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", "3")
    assert global_daily_turn_limit() == 1


def test_global_limit_env_var_overrides_the_derived_value(monkeypatch):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", "20")
    monkeypatch.setenv("GLOBAL_DAILY_LIMIT", "9")
    assert global_daily_turn_limit() == 9


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "2.5", "  ", ""])
def test_invalid_quota_values_fall_back_to_the_default(monkeypatch, bad):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", bad)
    assert daily_quota() == quota.DEFAULT_DAILY_QUOTA


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5"])
def test_invalid_global_override_is_ignored(monkeypatch, bad):
    monkeypatch.setenv("GLOBAL_DAILY_LIMIT", bad)
    assert global_daily_turn_limit() == 4


def test_guard_defaults_to_the_derived_global_limit(monkeypatch):
    monkeypatch.setenv("GEMINI_DAILY_QUOTA", "40")
    assert Guard(store=MemoryStore()).global_per_day == 8


async def test_fifth_turn_of_the_day_is_refused_with_default_quota():
    guard = Guard(store=MemoryStore(), ip_per_minute=100, ip_per_day=100)
    for n in range(4):
        await guard.check_request(f"10.0.0.{n}", None)  # four different visitors: allowed
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("10.0.0.99", None)
    assert exc.value.status_code == 503


# --- per-IP daily limit ------------------------------------------------------

@pytest.mark.parametrize(
    "global_limit, per_ip",
    [(4, 1), (6, 2), (9, 3), (20, 6), (300, 100), (3, 1), (2, 1), (1, 1)],
)
def test_ip_limit_is_a_third_of_the_global_limit_but_at_least_one(global_limit, per_ip):
    assert quota.ip_daily_turn_limit(global_limit) == per_ip


@pytest.mark.parametrize("global_limit", [3, 4, 7, 20, 100, 300])
def test_one_ip_never_gets_more_than_a_third_of_the_day(global_limit):
    assert quota.ip_daily_turn_limit(global_limit) * 3 <= global_limit


def test_default_guard_allows_each_ip_one_turn_per_day():
    guard = Guard(store=MemoryStore())
    assert (guard.global_per_day, guard.ip_per_day) == (4, 1)


def test_ip_limit_follows_a_global_override(monkeypatch):
    monkeypatch.setenv("GLOBAL_DAILY_LIMIT", "12")
    assert Guard(store=MemoryStore()).ip_per_day == 4


def test_ip_limit_follows_an_explicit_global_argument():
    assert Guard(store=MemoryStore(), global_per_day=30).ip_per_day == 10


def test_explicit_ip_limit_is_respected():
    assert Guard(store=MemoryStore(), ip_per_day=7).ip_per_day == 7


async def test_second_turn_from_the_same_ip_is_refused_but_other_ips_are_not():
    guard = Guard(store=MemoryStore(), ip_per_minute=100)
    await guard.check_request("1.1.1.1", None)
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("1.1.1.1", None)
    assert exc.value.status_code == 429
    await guard.check_request("2.2.2.2", None)  # a different visitor still gets their turn
