"""Gemini free-tier facts the app relies on.

The binding constraint for this demo is the provider's daily request quota (requests per day, RPD),
not money. The app does not meter it: when Gemini refuses a request with a 429, guards/errors.py turns
that into a friendly message. What lives here is how many requests one chat turn may make, and the
timing of Google's daily reset, which that message quotes.

Measured model requests per chat turn (tests/test_llm_call_budget.py drives the real runner and
agent tree with a scripted model and fails on any unscripted extra request):

    injection pre-check (no model call) ................. 0
    coordinator answers directly ........................ 1
    coordinator + specialist, no tool ................... 2
    coordinator + specialist + one tool round ........... 3
    specialist hands off to a second specialist + tool .. 4

Retries add none: with no retry options configured, google-genai uses a "never retry" strategy.
"""

# The most requests one turn may make. ADK enforces this (agent/runner_utils.py passes it as
# RunConfig.max_llm_calls) and counts *before* sending, so the request over the cap is never made.
# It is set to the longest measured path above. A turn that needs more than this fails with a
# generic error.
MAX_CALLS_PER_TURN = 4

# Shown only when a Gemini error names a per-day quota (guards/errors.py). The reset time is stated
# because Google's docs say daily request quotas reset at midnight Pacific time.
DAILY_QUOTA_MESSAGE = (
    "SHRED TECH's shared free-tier demo budget is used up for today. "
    "It will be back after the daily reset at midnight Pacific time."
)


# --- Daily reset --------------------------------------------------------------------

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("shred_tech.quota")

# Google resets the daily request quota at midnight Pacific time (Gemini API rate-limits docs:
# "Requests per day (RPD) quotas reset at midnight Pacific time"). The docs do not say how daylight
# saving is handled, so we follow the wall clock in America/Los_Angeles.
RESET_TIMEZONE_NAME = "America/Los_Angeles"
try:
    RESET_TIMEZONE = ZoneInfo(RESET_TIMEZONE_NAME)
except ZoneInfoNotFoundError:  # tzdata is a pinned dependency, so this should not happen
    from datetime import timezone

    logger.error("no time-zone data for %s; using fixed UTC-8 (off by 1h in summer)", RESET_TIMEZONE_NAME)
    RESET_TIMEZONE = timezone(timedelta(hours=-8))


def quota_day_window(now: float) -> tuple[int, int]:
    """(day number, seconds until the next reset) for the quota day containing `now`.

    The quota day runs midnight to midnight Pacific time, so our daily counters roll over at the same
    moment Google's quota does. Seconds are computed from absolute timestamps, so the 23- and 25-hour
    days around daylight-saving changes are handled correctly.
    """
    local = datetime.fromtimestamp(now, RESET_TIMEZONE)
    next_midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), RESET_TIMEZONE)
    return local.date().toordinal(), max(1, int(next_midnight.timestamp() - now))
