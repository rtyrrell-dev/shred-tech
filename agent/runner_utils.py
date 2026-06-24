import uuid
from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from agent.agent import root_agent
from agent.logging_utils import TurnLogger

APP_NAME = "shred_tech"

INITIAL_STATE = {
    "guitar_model": None,
    "bridge_type": None,
    "symptoms_mentioned": [],
}

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


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

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
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
