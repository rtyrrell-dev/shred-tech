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
