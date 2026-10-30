import uuid
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents.run_config import RunConfig
from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from agent.agent import root_agent
from agent.logging_utils import TurnLogger
from guards.abuse import GUARD_INSTRUCTION
from guards.budget import TurnState, current_turn
from guards.budget_plugin import RequestBudgetPlugin
from guards.quota import MAX_CALLS_PER_TURN

APP_NAME = "shred_tech"

INITIAL_STATE = {
    "guitar_model": None,
    "bridge_type": None,
    "symptoms_mentioned": [],
}

# Upper bound on model calls in one user turn. The value and how it was measured live in
# guards/quota.py; ADK's default of 500 would let a looping agent exhaust the daily quota.
MAX_LLM_CALLS_PER_TURN = MAX_CALLS_PER_TURN

session_service = InMemorySessionService()
# Scope/non-disclosure rules appended to every agent's prompt (the supported replacement for the
# deprecated LlmAgent.global_instruction field).
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    plugins=[GlobalInstructionPlugin(GUARD_INSTRUCTION), RequestBudgetPlugin()],
)


async def run_query(
    message: str,
    user_id: str = "user",
    session_id: str = None,
    turn: TurnState | None = None,
) -> tuple[str, str]:
    """Send a single message through the full agent tree.

    Returns:
        (response_text, agent_author) where agent_author is the name of the
        agent that produced the final substantive response.

    Every call is logged to logs/agentops.jsonl via TurnLogger.

    `turn` carries the shared-budget state for API traffic: each real Gemini request is charged to the
    budget before it is sent (guards/budget_plugin.py). Without it (eval scripts) nothing is metered.
    """
    session_id = session_id or str(uuid.uuid4())

    try:
        existing = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        existing = None

    if existing is None:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state=dict(INITIAL_STATE),
        )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    logger = TurnLogger(session_id=session_id, user_message=message)
    collected: list[tuple[str, str]] = []

    token = current_turn.set(turn)
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
            run_config=RunConfig(max_llm_calls=MAX_LLM_CALLS_PER_TURN),
        ):
            logger.observe(event)  # read-only — never touches session state

            if event.is_final_response():
                author = getattr(event, "author", "unknown")
                if event.content and event.content.parts:
                    text = "".join(
                        p.text for p in event.content.parts
                        if hasattr(p, "text") and p.text
                    )
                    if text.strip():
                        collected.append((text.strip(), author))

    finally:
        current_turn.reset(token)

    logger.flush()

    if collected:
        return collected[-1]
    return "", "unknown"
