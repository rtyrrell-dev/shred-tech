"""Errors reaching the client must be friendly and must never contain internals."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from guards.errors import GENERIC_MESSAGE, RATE_LIMIT_MESSAGE, TIMEOUT_MESSAGE, classify_error

SECRET_DETAIL = "internal-detail-api-key-leak-marker"


def _quota_error():
    return genai_errors.ClientError(
        429, {"error": {"code": 429, "message": SECRET_DETAIL, "status": "RESOURCE_EXHAUSTED"}}
    )


def test_quota_error_becomes_friendly_503_without_an_invented_retry_after():
    safe = classify_error(_quota_error())
    assert (safe.status_code, safe.detail) == (503, RATE_LIMIT_MESSAGE)
    assert safe.retry_after is None


def test_wrapped_quota_error_is_still_recognised():
    try:
        try:
            raise _quota_error()
        except genai_errors.ClientError as inner:
            raise RuntimeError("agent failed") from inner
    except RuntimeError as outer:
        assert classify_error(outer).status_code == 503


def test_timeout_becomes_504():
    safe = classify_error(asyncio.TimeoutError())
    assert (safe.status_code, safe.detail) == (504, TIMEOUT_MESSAGE)


def test_unknown_error_becomes_generic_500():
    safe = classify_error(ValueError(SECRET_DETAIL))
    assert (safe.status_code, safe.detail) == (500, GENERIC_MESSAGE)
    assert SECRET_DETAIL not in safe.detail


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app, raise_server_exceptions=False)


def test_endpoint_never_leaks_exception_text(client, monkeypatch):
    import api.main as main

    async def boom(**_):
        raise RuntimeError(SECRET_DETAIL)

    monkeypatch.setattr(main, "run_query", boom)
    res = client.post("/api/agent", json={"message": "hello"})
    assert res.status_code == 500
    assert SECRET_DETAIL not in res.text


def test_endpoint_quota_error_is_friendly(client, monkeypatch):
    import api.main as main

    async def boom(**_):
        raise _quota_error()

    monkeypatch.setattr(main, "run_query", boom)
    res = client.post("/api/agent", json={"message": "hello"})
    assert res.status_code == 503
    assert res.json()["detail"] == RATE_LIMIT_MESSAGE
    assert "retry-after" not in res.headers
    assert SECRET_DETAIL not in res.text


def test_endpoint_per_day_quota_error_names_the_daily_reset(client, monkeypatch):
    import api.main as main
    from guards.quota import DAILY_QUOTA_MESSAGE

    async def boom(**_):
        raise genai_errors.ClientError(
            429,
            {
                "error": {
                    "code": 429,
                    "message": SECRET_DETAIL,
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}],
                }
            },
        )

    monkeypatch.setattr(main, "run_query", boom)
    res = client.post("/api/agent", json={"message": "hello"})
    assert res.status_code == 503
    assert res.json()["detail"] == DAILY_QUOTA_MESSAGE
    assert 1 <= int(res.headers["retry-after"]) <= 25 * 3600  # seconds to the next Pacific midnight
    assert SECRET_DETAIL not in res.text


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_disabled(client, path):
    assert client.get(path).status_code == 404
