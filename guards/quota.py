"""Free-tier request-quota budgeting for the Gemini API.

The binding constraint for this demo is the daily request quota (requests per day, RPD), not money.
Everything below is derived from two facts: how many requests the provider allows per day, and how
many requests one chat turn can make.

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
# It is set to the longest measured path above, which makes the daily-quota math below a guarantee
# instead of an estimate. A turn that needs more than this fails with a generic error.
MAX_CALLS_PER_TURN = 4

# Shown when the daily free-tier quota is used up. The reset time is stated because Google's docs say
# daily request quotas reset at midnight Pacific time.
DAILY_QUOTA_MESSAGE = (
    "SHRED TECH has used up its daily free-tier quota for the Gemini API. "
    "It will be back after the quota resets at midnight Pacific time."
)


# --- Daily quota --------------------------------------------------------------------

import logging
import os
from datetime import datetime, timedelta
from fractions import Fraction
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("shred_tech.quota")

# Free-tier daily request quota (RPD) for the key. Google does not publish a fixed number for a
# model, so it is configuration: set GEMINI_DAILY_QUOTA to what AI Studio shows for your project.
DEFAULT_DAILY_QUOTA = 20

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


def quota_date_key(now: float) -> str:
    """The Pacific-time calendar date (YYYY-MM-DD) of the quota day containing `now`."""
    return datetime.fromtimestamp(now, RESET_TIMEZONE).date().isoformat()


def quota_day_window(now: float) -> tuple[int, int]:
    """(day number, seconds until the next reset) for the quota day containing `now`.

    The quota day runs midnight to midnight Pacific time, so our daily counters roll over at the same
    moment Google's quota does. Seconds are computed from absolute timestamps, so the 23- and 25-hour
    days around daylight-saving changes are handled correctly.
    """
    local = datetime.fromtimestamp(now, RESET_TIMEZONE)
    next_midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), RESET_TIMEZONE)
    return local.date().toordinal(), max(1, int(next_midnight.timestamp() - now))


def _positive_int_env(name: str) -> int | None:
    """A positive integer from the environment, or None if unset or invalid (with a warning)."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        value = 0
    if value < 1:
        logger.warning("ignoring %s=%r: expected a positive integer", name, raw)
        return None
    return value


def daily_quota() -> int:
    """GEMINI_DAILY_QUOTA, defaulting to 20 requests per day."""
    return _positive_int_env("GEMINI_DAILY_QUOTA") or DEFAULT_DAILY_QUOTA


# --- Daily quota -> request budget ------------------------------------------------------------

# Fraction of the daily quota the demo may spend. The demo runs on its own Google project, so most of
# the quota is ours to use; the remainder is slack for anything unmetered (see SECURITY.md) and for
# the moment where our counter and Google's disagree.
DEFAULT_QUOTA_SAFETY = Fraction(9, 10)


def quota_safety() -> Fraction:
    """GEMINI_QUOTA_SAFETY as an exact fraction in (0, 1]; the default 0.9 if unset or invalid."""
    raw = os.environ.get("GEMINI_QUOTA_SAFETY")
    if raw is None or not raw.strip():
        return DEFAULT_QUOTA_SAFETY
    try:
        value = Fraction(raw.strip())
    except (ValueError, ZeroDivisionError):
        value = Fraction(0)
    if not 0 < value <= 1:
        logger.warning("ignoring GEMINI_QUOTA_SAFETY=%r: expected a number above 0 and at most 1", raw)
        return DEFAULT_QUOTA_SAFETY
    return value


def daily_request_budget() -> int:
    """Gemini requests the demo may make per day, shared by all visitors: floor(quota x safety).

    Computed with exact fractions (floats would turn 100 x 0.57 into 56.99999999999999 and floor it
    to 56). At least 1, so a tiny quota does not switch the demo off entirely.
    """
    return max(1, int(daily_quota() * quota_safety()))  # int() floors a positive Fraction
