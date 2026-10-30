"""A scripted stand-in for the Gemini call, shared by the metering tests.

The real runner, agent tree and plugins run; only the network call is replaced. Each script item is
either an LlmResponse (returned for that model request) or an exception (raised, to simulate a
provider failure). The fake raises if the framework makes a request the script did not expect.
"""

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def say(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def call(name, **args):
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return LlmResponse(content=types.Content(role="model", parts=[part]))


def transfer(agent_name):
    return call("transfer_to_agent", agent_name=agent_name)


def install(monkeypatch, script):
    """Patch the Gemini call with `script`; returns the list that records every model request."""
    script = list(script)
    requests = []

    async def fake_generate(self, llm_request, stream=False):
        requests.append(llm_request)
        if len(requests) > len(script):
            raise AssertionError(f"unscripted model request #{len(requests)}")
        item = script[len(requests) - 1]
        if isinstance(item, Exception):
            raise item
        yield item

    monkeypatch.setattr(Gemini, "generate_content_async", fake_generate)
    return requests


def install_always(monkeypatch, text="hi"):
    """Patch the Gemini call so every request is answered with `text`; records each request."""
    requests = []

    async def fake_generate(self, llm_request, stream=False):
        requests.append(llm_request)
        yield say(text)

    monkeypatch.setattr(Gemini, "generate_content_async", fake_generate)
    return requests
