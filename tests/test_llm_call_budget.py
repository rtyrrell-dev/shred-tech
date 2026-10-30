"""Measures how many Gemini requests one chat turn makes on each path.

The real runner and the real agent tree run; only the model call is replaced by a scripted fake.
The fake raises if the framework makes a call the script did not expect, so any hidden extra call
(for example the coordinator being called again after a hand-off) shows up as a failure rather
than being silently undercounted.

The 4-call maximum is the per-turn cap (guards/quota.py).
"""

import uuid

import pytest
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types

import agent.runner_utils as runner_utils
from guards.quota import MAX_CALLS_PER_TURN


def say(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def call(name, **args):
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return LlmResponse(content=types.Content(role="model", parts=[part]))


def transfer(agent_name):
    return call("transfer_to_agent", agent_name=agent_name)


@pytest.fixture
def scripted_model(monkeypatch):
    """Replace the network call with a script; returns a list recording every model request."""
    requests = []

    def install(script):
        script = list(script)

        async def fake_generate(self, llm_request, stream=False):
            requests.append(llm_request)
            if len(requests) > len(script):
                raise AssertionError(
                    f"unscripted model call #{len(requests)}: the framework made an extra request"
                )
            yield script[len(requests) - 1]

        monkeypatch.setattr(Gemini, "generate_content_async", fake_generate)
        return requests

    return install


async def run_turn(message="my strat buzzes"):
    return await runner_utils.run_query(message, session_id=f"budget-{uuid.uuid4()}")


async def test_coordinator_only_turn_is_1_call(scripted_model):
    requests = scripted_model([say("Are you looking to dial in a spec, or did something change?")])
    await run_turn("my action feels off")
    assert len(requests) == 1


async def test_coordinator_plus_specialist_without_tool_is_2_calls(scripted_model):
    requests = scripted_model([transfer("TroubleshootingAgent"), say("Which strings buzz?")])
    reply, author = await run_turn()
    assert len(requests) == 2
    assert author == "TroubleshootingAgent"


async def test_coordinator_plus_specialist_with_one_tool_is_3_calls(scripted_model):
    requests = scripted_model(
        [
            transfer("SetupAgent"),
            call("get_setup_flow", bridge_type="strat"),
            say("Step 1: pre-setup."),
        ]
    )
    await run_turn("set up my strat")
    assert len(requests) == 3


async def test_specialist_handing_off_to_another_specialist_is_4_calls(scripted_model):
    requests = scripted_model(
        [
            transfer("SetupAgent"),
            transfer("TroubleshootingAgent"),
            call("diagnose_issue", symptom="buzzing"),
            say("Likely neck relief."),
        ]
    )
    reply, author = await run_turn()
    assert len(requests) == 4
    assert author == "TroubleshootingAgent"


async def test_runaway_tool_loop_is_cut_off_at_the_per_turn_cap(scripted_model):
    cap = runner_utils.MAX_LLM_CALLS_PER_TURN
    loop = [transfer("TroubleshootingAgent")] + [call("diagnose_issue", symptom="buzzing")] * (cap + 5)
    requests = scripted_model(loop)
    with pytest.raises(LlmCallsLimitExceededError):
        await run_turn()
    # ADK counts before sending, so the request over the cap is never made.
    assert len(requests) == cap


def test_per_turn_cap_equals_the_longest_measured_path():
    # The quota math assumes no turn exceeds the cap, so the cap must cover the longest supported
    # path (the 4-call specialist hand-off above) and must not be padded beyond what was measured.
    assert runner_utils.MAX_LLM_CALLS_PER_TURN == MAX_CALLS_PER_TURN == 4


def test_no_retries_are_configured_for_gemini_requests():
    # With retry_options unset the google-genai client uses a "never retry" strategy, so a failed
    # request is not silently re-sent (and re-counted against the daily quota).
    from agent.agent import root_agent

    assert Gemini().retry_options is None
    assert all(a.model == "gemini-2.5-flash" for a in [root_agent, *root_agent.sub_agents])


async def test_follow_up_turns_in_one_session_skip_the_coordinator(scripted_model):
    # Documented in the README and SECURITY.md: once a specialist has answered, the next message in
    # the same session goes straight to it, so a follow-up costs 1-2 requests instead of 2-4.
    requests = scripted_model(
        [
            transfer("SetupAgent"),                           # turn 1: coordinator routes ...
            call("get_setup_flow", bridge_type="strat"),      # ... specialist uses a tool ...
            say("Step 1: pre-setup."),                        # ... and answers (3 requests)
            say("Step 2: truss rod."),                        # turn 2: specialist answers (1 request)
            call("get_setup_flow", bridge_type="strat"),      # turn 3: specialist uses a tool ...
            say("Here is the order."),                        # ... and answers (2 requests)
        ]
    )
    sid = f"follow-up-{uuid.uuid4()}"
    costs = []
    for message in ("set up my strat", "done, what next?", "and the order again?"):
        before = len(requests)
        await runner_utils.run_query(message, session_id=sid)
        costs.append(len(requests) - before)
    assert costs == [3, 1, 2]
