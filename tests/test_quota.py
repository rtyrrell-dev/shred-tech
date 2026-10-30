from guards import quota
from guards.quota import MAX_CALLS_PER_TURN


def test_per_turn_cap_is_still_4_model_requests():
    assert MAX_CALLS_PER_TURN == 4


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
