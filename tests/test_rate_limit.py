import pytest
from fastapi.testclient import TestClient

import api.main as main
from guards import ratelimit
from guards.ratelimit import (
    Guard,
    GuardUnavailable,
    LimitExceeded,
    MemoryStore,
    UpstashStore,
    build_store_from_env,
    client_ip,
)


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def make_guard(**overrides):
    clock = overrides.pop("clock", Clock())
    # Daily limits default to the tiny free-tier values; these tests exercise other limits, so give
    # the daily ones headroom unless a test sets them explicitly.
    overrides.setdefault("global_per_day", 1000)
    return Guard(store=MemoryStore(clock), clock=clock, **overrides), clock


# --- per-IP limits --------------------------------------------------------

async def test_ip_minute_limit_blocks_then_recovers_next_window():
    guard, clock = make_guard(ip_per_minute=3)
    for _ in range(3):
        await guard.check_request("1.1.1.1", None)
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("1.1.1.1", None)
    assert exc.value.status_code == 429 and 0 < exc.value.retry_after <= 60
    clock.now += 61
    await guard.check_request("1.1.1.1", None)


async def test_limits_are_per_ip():
    guard, _ = make_guard(ip_per_minute=1)
    await guard.check_request("1.1.1.1", None)
    await guard.check_request("2.2.2.2", None)  # a different IP is unaffected
    with pytest.raises(LimitExceeded):
        await guard.check_request("1.1.1.1", None)


async def test_omitting_session_id_does_not_dodge_ip_limit():
    # The old limiter keyed on a client-chosen session id; sending a new/no id each time reset it.
    guard, _ = make_guard(ip_per_minute=2)
    await guard.check_request("1.1.1.1", None)
    await guard.check_request("1.1.1.1", "made-up-id")
    with pytest.raises(LimitExceeded):
        await guard.check_request("1.1.1.1", None)


# --- global budget circuit breaker ---------------------------------------

async def test_global_daily_cap_returns_503_for_everyone():
    guard, _ = make_guard(global_per_day=2, ip_per_minute=100)
    await guard.check_request("1.1.1.1", None)
    await guard.check_request("2.2.2.2", None)
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("3.3.3.3", None)
    assert exc.value.status_code == 503


# --- sessions ------------------------------------------------------------

async def test_new_session_is_server_issued_and_then_honoured():
    guard, _ = make_guard()
    sid = await guard.check_request("1.1.1.1", None)
    assert await guard.check_request("1.1.1.1", sid) == sid


async def test_client_chosen_session_id_is_replaced():
    guard, _ = make_guard()
    sid = await guard.check_request("1.1.1.1", "attacker-picked-id")
    assert sid != "attacker-picked-id"


async def test_session_message_cap():
    guard, _ = make_guard(session_max_messages=2, ip_per_minute=100)
    sid = await guard.check_request("1.1.1.1", None)
    await guard.check_request("1.1.1.1", sid)
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("1.1.1.1", sid)
    assert "New session" in exc.value.message


# --- fail closed ---------------------------------------------------------

class BrokenStore:
    async def incr_window(self, key, ttl):
        raise ConnectionError("redis down")

    async def exists(self, key):
        raise ConnectionError("redis down")

    async def set_with_ttl(self, key, ttl):
        raise ConnectionError("redis down")


async def test_store_outage_fails_closed():
    with pytest.raises(GuardUnavailable):
        await Guard(store=BrokenStore()).check_request("1.1.1.1", None)


async def test_missing_store_fails_closed():
    with pytest.raises(GuardUnavailable):
        await Guard(store=None).check_request("1.1.1.1", None)


def test_unconfigured_store_fails_closed_by_default(monkeypatch):
    # No Upstash credentials and no explicit local-dev flag => no store => requests are refused.
    # Note the VERCEL variable is deliberately absent: Vercel only exposes it when a project
    # setting is on, so a missing VERCEL must never be what keeps protection enabled.
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("SHRED_LOCAL_DEV", raising=False)
    assert build_store_from_env() is None


def test_in_memory_limiter_requires_explicit_local_dev_flag(monkeypatch):
    monkeypatch.setenv("SHRED_LOCAL_DEV", "1")
    assert isinstance(build_store_from_env(), MemoryStore)


def test_local_dev_flag_must_be_exactly_one(monkeypatch):
    for value in ("0", "true", "yes", ""):
        monkeypatch.setenv("SHRED_LOCAL_DEV", value)
        assert build_store_from_env() is None


def test_upstash_credentials_build_upstash_store(monkeypatch):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://example.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "not-a-real-token")
    assert isinstance(build_store_from_env(), UpstashStore)


def test_legacy_kv_variable_names_are_accepted(monkeypatch):
    monkeypatch.setenv("KV_REST_API_URL", "https://example.upstash.io")
    monkeypatch.setenv("KV_REST_API_TOKEN", "not-a-real-token")
    assert isinstance(build_store_from_env(), UpstashStore)


async def test_upstash_store_sets_expiry_only_on_first_hit():
    calls = []

    class FakeRedis:
        n = 0

        async def incr(self, key):
            self.n += 1
            calls.append(("incr", key))
            return self.n

        async def expire(self, key, seconds):
            calls.append(("expire", key, seconds))

    store = UpstashStore(FakeRedis())
    await store.incr_window("k", 120)
    await store.incr_window("k", 120)
    assert [c[0] for c in calls] == ["incr", "expire", "incr"]


# --- client IP -----------------------------------------------------------

def test_forwarded_headers_ignored_in_local_dev(monkeypatch):
    monkeypatch.setenv("SHRED_LOCAL_DEV", "1")
    assert client_ip({"x-real-ip": "9.9.9.9"}, "5.5.5.5") == "5.5.5.5"


def test_real_ip_header_trusted_by_default(monkeypatch):
    assert client_ip({"x-real-ip": "9.9.9.9"}, "10.0.0.1") == "9.9.9.9"
    assert client_ip({"x-vercel-forwarded-for": "8.8.8.8, 1.1.1.1"}, None) == "8.8.8.8"


def test_raw_x_forwarded_for_is_never_used(monkeypatch):
    assert client_ip({"x-forwarded-for": "6.6.6.6"}, "10.0.0.1") == "10.0.0.1"


def test_ipv6_is_grouped_by_64():
    a = client_ip({"x-real-ip": "2001:db8:1:2:aaaa::1"}, None)
    b = client_ip({"x-real-ip": "2001:db8:1:2:bbbb::9"}, None)
    assert a == b


def test_garbage_ip_collapses_to_unknown():
    assert client_ip({}, "not-an-ip") == "unknown"


# --- through the HTTP API ------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    async def ok(**_):
        return "ok", "SetupAgent"

    monkeypatch.setattr(main, "run_query", ok)
    return TestClient(main.app)


def test_api_issues_session_and_reuses_it(client):
    first = client.post("/api/agent", json={"message": "hi"}).json()["session_id"]
    second = client.post("/api/agent", json={"message": "hi", "session_id": first}).json()
    assert second["session_id"] == first


def test_api_replaces_unknown_session_id(client):
    res = client.post("/api/agent", json={"message": "hi", "session_id": "abc-123"})
    assert res.json()["session_id"] != "abc-123"


def test_api_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(main, "guard", Guard(store=MemoryStore(), ip_per_minute=1))
    assert client.post("/api/agent", json={"message": "hi"}).status_code == 200
    res = client.post("/api/agent", json={"message": "hi"})
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) > 0
    assert "too quickly" in res.json()["detail"]


def test_api_fails_closed_when_store_missing(client, monkeypatch):
    monkeypatch.setattr(main, "guard", Guard(store=None))
    res = client.post("/api/agent", json={"message": "hi"})
    assert res.status_code == 503
    assert res.json()["detail"] == ratelimit.UNAVAILABLE_MESSAGE
