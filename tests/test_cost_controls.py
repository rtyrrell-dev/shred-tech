from fastapi.testclient import TestClient

import agent.runner_utils as runner_utils
import api.main as main
from agent.agent import MAX_OUTPUT_TOKENS, root_agent

ALLOWED_MODELS = {"gemini-2.5-flash"}


def _all_agents(agent):
    yield agent
    for sub in agent.sub_agents:
        yield from _all_agents(sub)


def test_every_agent_has_an_output_token_ceiling():
    agents = list(_all_agents(root_agent))
    assert len(agents) == 4  # coordinator + three specialists
    for a in agents:
        assert a.generate_content_config.max_output_tokens == MAX_OUTPUT_TOKENS


def test_models_are_fixed_server_side():
    for a in _all_agents(root_agent):
        assert a.model in ALLOWED_MODELS


def test_client_cannot_choose_the_model(monkeypatch):
    calls = []

    async def fake_run_query(**kwargs):
        calls.append(kwargs)
        return "ok", "SetupAgent"

    monkeypatch.setattr(main, "run_query", fake_run_query)
    client = TestClient(main.app)
    res = client.post(
        "/api/agent", json={"message": "hi", "model": "gemini-2.5-pro", "max_output_tokens": 99999}
    )
    assert res.status_code == 200
    assert set(calls[0]) == {"message", "user_id", "session_id", "turn"}
    assert "model" not in main.ChatRequest.model_fields


def test_run_query_limits_llm_calls_per_turn(monkeypatch):
    import asyncio

    captured = {}

    async def fake_run_async(**kwargs):
        captured.update(kwargs)
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(runner_utils.runner, "run_async", fake_run_async)
    asyncio.run(runner_utils.run_query("hi", session_id="test-session"))
    assert captured["run_config"].max_llm_calls == runner_utils.MAX_LLM_CALLS_PER_TURN
    assert runner_utils.MAX_LLM_CALLS_PER_TURN < 500
