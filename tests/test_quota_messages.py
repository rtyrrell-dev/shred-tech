import time

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

import api.main as main
from guards.errors import RATE_LIMIT_MESSAGE, classify_error
from guards.quota import DAILY_QUOTA_MESSAGE, IP_DAILY_MESSAGE, quota_day_window
from guards.ratelimit import Guard, MemoryStore

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


def test_daily_message_explains_the_free_tier_quota_and_the_documented_reset():
    assert "daily free-tier quota" in DAILY_QUOTA_MESSAGE
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


@pytest.fixture
def client(monkeypatch):
    async def ok(**_):
        return "ok", "SetupAgent"

    monkeypatch.setattr(main, "run_query", ok)
    return TestClient(main.app)


def test_hitting_our_global_cap_returns_the_daily_503(client, monkeypatch):
    monkeypatch.setattr(main, "guard", Guard(store=MemoryStore(), global_per_day=1, ip_per_minute=100))
    assert client.post("/api/agent", json={"message": "hi"}).status_code == 200
    # A different visitor: the global cap, not the per-IP cap, is what stops them.
    monkeypatch.setattr(main, "client_ip", lambda headers, peer: "9.9.9.9")
    res = client.post("/api/agent", json={"message": "hi"})
    assert res.status_code == 503
    assert res.json()["detail"] == DAILY_QUOTA_MESSAGE
    assert 1 <= int(res.headers["retry-after"]) <= 25 * 3600


def test_hitting_the_per_ip_daily_limit_explains_the_free_tier_and_reset(client, monkeypatch):
    guard = Guard(store=MemoryStore(), global_per_day=30, ip_per_day=1, ip_per_minute=100)
    monkeypatch.setattr(main, "guard", guard)
    client.post("/api/agent", json={"message": "hi"})
    res = client.post("/api/agent", json={"message": "hi"})
    assert res.status_code == 429
    assert res.json()["detail"] == IP_DAILY_MESSAGE
    assert "midnight Pacific time" in IP_DAILY_MESSAGE


def test_retry_after_reflects_the_real_time_to_reset(client, monkeypatch):
    guard = Guard(store=MemoryStore(), global_per_day=30, ip_per_day=1, ip_per_minute=100)
    monkeypatch.setattr(main, "guard", guard)
    client.post("/api/agent", json={"message": "hi"})
    res = client.post("/api/agent", json={"message": "hi"})
    expected = quota_day_window(time.time())[1]
    assert abs(int(res.headers["retry-after"]) - expected) <= 5
