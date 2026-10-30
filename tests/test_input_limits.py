import asyncio

import pytest
from fastapi.testclient import TestClient

import api.main as main
from guards.limits import MAX_BODY_BYTES


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def fast_model(monkeypatch):
    async def ok(**_):
        return "ok", "SetupAgent"

    monkeypatch.setattr(main, "run_query", ok)
    main._rate_limit_store.clear()


def test_normal_message_passes(client):
    assert client.post("/api/agent", json={"message": "hi"}).status_code == 200


def test_declared_oversized_body_is_rejected_with_413(client):
    body = '{"message": "' + "a" * (MAX_BODY_BYTES + 10) + '"}'
    res = client.post("/api/agent", content=body, headers={"content-type": "application/json"})
    assert res.status_code == 413


def test_streamed_oversized_body_without_content_length_is_rejected(client):
    def chunks():
        yield b'{"message": "'
        for _ in range(MAX_BODY_BYTES // 1024 + 2):
            yield b"a" * 1024
        yield b'"}'

    res = client.post("/api/agent", content=chunks(), headers={"content-type": "application/json"})
    assert res.status_code == 413


def test_message_over_char_limit_is_rejected_by_validation(client):
    res = client.post("/api/agent", json={"message": "a" * (main.MAX_MESSAGE_LENGTH + 1)})
    assert res.status_code == 422


def test_slow_model_call_times_out_with_504(client, monkeypatch):
    async def slow(**_):
        await asyncio.sleep(5)
        return "late", "SetupAgent"

    monkeypatch.setattr(main, "run_query", slow)
    monkeypatch.setattr(main, "REQUEST_TIMEOUT_SECONDS", 0.05)
    res = client.post("/api/agent", json={"message": "hi"})
    assert res.status_code == 504
