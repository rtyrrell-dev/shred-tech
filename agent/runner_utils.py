import secrets
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
    plugins=[GlobalInstructionPlugin(GUARD_INSTRUCTION)],
)


async def resolve_session_id(claimed: str | None, user_id: str = "user") -> str:
    """The session id to use for a request: the client's, if this instance issued it, else a new one.

    Ids are generated here, from the `secrets` module, and bound to the ADK session service: a claimed
    id is honoured only if the service already holds that session. An unknown id (never issued, issued
    by another serverless instance, or lost when this instance was recycled) is not an error: the
    client simply gets a fresh server-issued id in the response and starts a new conversation. The
    client therefore cannot mint ids, and a random 128-bit id cannot be guessed to join someone else's.
    """
    if claimed:
        try:
            existing = await session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=claimed
            )
        except Exception:
            existing = None
        if existing is not None:
            return claimed

    new_id = secrets.token_hex(16)
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=new_id, state=dict(INITIAL_STATE)
    )
    return new_id


async def run_query(
    message: str,
    user_id: str = "user",
    session_id: str = None,
) -> tuple[str, str]:
    """Send a single message through the full agent tree.

    Returns:
        (response_text, agent_author) where agent_author is the name of the
        agent that produced the final substantive response.

    Every call is logged to logs/agentops.jsonl via TurnLogger.
    """
    session_id = session_id or secrets.token_hex(16)

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

    logger.flush()

    if collected:
        return collected[-1]
    return "", "unknown"
