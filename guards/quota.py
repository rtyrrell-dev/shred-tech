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

# --- Daily quota -> turns --------------------------------------------------------------------

import logging
import os

logger = logging.getLogger("shred_tech.quota")

# Free-tier daily request quota (RPD) for the key. Google does not publish a fixed number for a
# model, so it is configuration: set GEMINI_DAILY_QUOTA to what AI Studio shows for your project.
DEFAULT_DAILY_QUOTA = 20

# Use at most 80% of the quota for chat turns. The rest absorbs anything else sharing the project's
# quota (evals, local development with the same key) and the window where our counter and Google's
# disagree. Quotas are per project, not per key, so a second key in the same project shares them.
SAFETY_PERCENT = 80


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


def global_daily_turn_limit() -> int:
    """Chat turns allowed per day across all users.

    floor(quota * 0.8 / MAX_CALLS_PER_TURN), computed with integers so there is no float rounding.
    Because no turn can make more than MAX_CALLS_PER_TURN requests, serving this many turns can
    never use more than 80% of the quota. GLOBAL_DAILY_LIMIT overrides the derived value.
    At least 1: with a tiny quota the margin cannot be honoured, but the demo still serves one turn.
    """
    override = _positive_int_env("GLOBAL_DAILY_LIMIT")
    if override is not None:
        return override
    return max(1, daily_quota() * SAFETY_PERCENT // (100 * MAX_CALLS_PER_TURN))
