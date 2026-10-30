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
