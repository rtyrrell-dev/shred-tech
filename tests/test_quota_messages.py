import pytest
from google.genai import errors as genai_errors

from guards.errors import RATE_LIMIT_MESSAGE, classify_error
from guards.quota import DAILY_QUOTA_MESSAGE

DAY_QUOTA_ID = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
MINUTE_QUOTA_ID = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"


def gemini_429(quota_id=None):
    error = {
        "code": 429,
        "message": "quota detail that must not reach users",
        "status": "RESOURCE_EXHAUSTED",
    }
    if quota_id:
        error["details"] = [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaMetric": "generate_content_requests", "quotaId": quota_id}],
            }
        ]
    return genai_errors.ClientError(429, {"error": error})


def test_daily_message_says_the_shared_free_tier_budget_is_used_up_and_when_it_resets():
    assert "shared free-tier demo budget" in DAILY_QUOTA_MESSAGE
    assert "used up for today" in DAILY_QUOTA_MESSAGE
    assert "midnight Pacific time" in DAILY_QUOTA_MESSAGE  # Gemini rate-limits docs state this reset


def test_provider_per_day_quota_error_gets_the_daily_message_with_exact_retry_after():
    safe = classify_error(gemini_429(DAY_QUOTA_ID))
    assert (safe.status_code, safe.detail) == (503, DAILY_QUOTA_MESSAGE)
    assert 1 <= safe.retry_after <= 25 * 3600  # seconds until the next Pacific midnight


@pytest.mark.parametrize("quota_id", [MINUTE_QUOTA_ID, None])
def test_other_429s_do_not_claim_the_daily_quota_is_used_up(quota_id):
    safe = classify_error(gemini_429(quota_id))
    assert safe.detail == RATE_LIMIT_MESSAGE
    assert "daily" not in safe.detail.lower() and "midnight" not in safe.detail.lower()
    assert safe.retry_after == 60


@pytest.mark.parametrize("quota_id", [DAY_QUOTA_ID, None])
def test_provider_error_text_never_reaches_the_user(quota_id):
    assert "must not reach users" not in classify_error(gemini_429(quota_id)).detail
