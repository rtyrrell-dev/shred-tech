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
    guard = Guard(store=MemoryStore(), ip_per_minute=100)
    for n in range(4):
        await guard.check_request(f"10.0.0.{n}", None)  # four different visitors: allowed
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("10.0.0.99", None)
    assert exc.value.status_code == 503


# --- the quota day matches Google's reset (midnight Pacific time) ------------

from datetime import datetime, timezone  # noqa: E402


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


def test_summer_reset_is_07_00_utc():
    # 2026-10-29 is in daylight time (UTC-7): Pacific midnight is 07:00 UTC.
    before = quota.quota_day_window(utc(2026, 10, 29, 6, 59, 59))
    after = quota.quota_day_window(utc(2026, 10, 29, 7, 0, 0))
    assert after[0] == before[0] + 1  # the day number changes exactly at 07:00:00 UTC
    assert before[1] == 1             # one second left at 06:59:59 UTC
    assert after[1] == 24 * 3600


def test_winter_reset_is_08_00_utc():
    before = quota.quota_day_window(utc(2026, 1, 15, 7, 59, 59))
    after = quota.quota_day_window(utc(2026, 1, 15, 8, 0, 0))
    assert after[0] == before[0] + 1
    assert after[1] == 24 * 3600


def test_daylight_saving_end_day_is_25_hours_long():
    # Clocks go back on 2026-11-01: that Pacific day lasts 25 hours.
    start = quota.quota_day_window(utc(2026, 11, 1, 7, 0, 0))
    assert start[1] == 25 * 3600


def test_daylight_saving_start_day_is_23_hours_long():
    start = quota.quota_day_window(utc(2026, 3, 8, 8, 0, 0))
    assert start[1] == 23 * 3600


def test_utc_midnight_is_not_a_reset():
    # The old counter rolled over at 00:00 UTC; Google's quota does not.
    a = quota.quota_day_window(utc(2026, 10, 28, 23, 59, 59))
    b = quota.quota_day_window(utc(2026, 10, 29, 0, 0, 1))
    assert a[0] == b[0]


async def test_daily_counters_reset_at_pacific_midnight_not_utc_midnight():
    from guards.ratelimit import Guard, LimitExceeded, MemoryStore

    now = [utc(2026, 10, 29, 6, 0, 0)]
    clock = lambda: now[0]  # noqa: E731
    guard = Guard(store=MemoryStore(clock), clock=clock, global_per_day=1, ip_per_minute=100)
    await guard.check_request("1.1.1.1", None)

    now[0] = utc(2026, 10, 29, 6, 59, 59)  # still the same quota day
    with pytest.raises(LimitExceeded) as exc:
        await guard.check_request("2.2.2.2", None)
    assert exc.value.retry_after == 1  # tells the client exactly when the reset is

    now[0] = utc(2026, 10, 29, 7, 0, 0)  # Pacific midnight: counters reset
    await guard.check_request("2.2.2.2", None)
