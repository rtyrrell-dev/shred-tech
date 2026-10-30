"""ADK plugin that charges the shared daily budget one unit per real Gemini request.

`before_model_callback` runs before every model request made by any agent in the tree. We spend one
unit from the budget first; if the budget is used up (or the store is down) we return a friendly
response instead, which tells ADK to skip the model call. So an over-budget request is never sent to
Google, and a turn that runs out of budget part-way ends cleanly instead of failing.
"""

from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from guards.budget import BudgetExhausted, current_turn
from guards.quota import DAILY_QUOTA_MESSAGE
from guards.ratelimit import UNAVAILABLE_MESSAGE, GuardUnavailable


def _reply(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


class RequestBudgetPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="request_budget")

    async def before_model_callback(self, *, callback_context, llm_request):
        turn = current_turn.get()
        if turn is None:
            return None  # unmetered caller (see guards/budget.py)

        if turn.exhausted is not None:  # already refused earlier in this turn; never call the model
            return _reply(DAILY_QUOTA_MESSAGE)
        if turn.unavailable:
            return _reply(UNAVAILABLE_MESSAGE)

        try:
            await turn.budget.take()
        except BudgetExhausted as exhausted:
            turn.exhausted = exhausted
            return _reply(DAILY_QUOTA_MESSAGE)
        except GuardUnavailable:
            turn.unavailable = True
            return _reply(UNAVAILABLE_MESSAGE)

        turn.calls += 1
        return None
