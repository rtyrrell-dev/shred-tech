"""Session ids are issued by the server and bound to the ADK session service."""

import re

import pytest
from fastapi.testclient import TestClient

import agent.runner_utils as runner_utils
import api.main as main


@pytest.fixture
def client(monkeypatch):
    async def ok(**_):
        return "ok", "SetupAgent"

    monkeypatch.setattr(main, "run_query", ok)
    return TestClient(main.app)


def test_first_request_gets_a_server_issued_id(client):
    sid = client.post("/api/agent", json={"message": "hi"}).json()["session_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", sid)  # 128 random bits from the secrets module


def test_issued_ids_are_unique(client):
    ids = {client.post("/api/agent", json={"message": "hi"}).json()["session_id"] for _ in range(5)}
    assert len(ids) == 5


def test_a_known_id_is_reused(client):
    first = client.post("/api/agent", json={"message": "hi"}).json()["session_id"]
    second = client.post("/api/agent", json={"message": "hi", "session_id": first}).json()
    assert second["session_id"] == first


def test_an_unknown_id_gets_a_fresh_one_not_an_error(client):
    res = client.post("/api/agent", json={"message": "hi", "session_id": "abc-123"})
    assert res.status_code == 200
    assert res.json()["session_id"] != "abc-123"


async def test_issued_id_exists_in_the_session_service_and_claimed_id_does_not_get_created():
    sid = await runner_utils.resolve_session_id(None)
    stored = await runner_utils.session_service.get_session(
        app_name=runner_utils.APP_NAME, user_id="user", session_id=sid
    )
    assert stored is not None

    other = await runner_utils.resolve_session_id("client-picked-id")
    assert other != "client-picked-id"
    missing = await runner_utils.session_service.get_session(
        app_name=runner_utils.APP_NAME, user_id="user", session_id="client-picked-id"
    )
    assert missing is None
