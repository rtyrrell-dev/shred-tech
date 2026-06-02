import os
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from agent.agent import root_agent

session_service = InMemorySessionService()
APP_NAME = "shred_tech"

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

# Rate limiting: max requests per window per session
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes
_rate_limit_store: dict[str, deque] = defaultdict(deque)

MAX_MESSAGE_LENGTH = 2000


def check_rate_limit(session_id: str) -> bool:
    """Returns True if the request is allowed, False if rate limited."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _rate_limit_store[session_id]

    # Drop timestamps outside the window
    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return False

    timestamps.append(now)
    return True


def sanitize_input(text: str) -> str:
    """Strip null bytes and non-printable control characters (preserve newlines and tabs)."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="SHRED TECH API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty.")
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message exceeds {MAX_MESSAGE_LENGTH} character limit.")
        return v

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-zA-Z0-9\-]{1,64}$", v):
            raise ValueError("Invalid session_id format.")
        return v


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.get("/health")
async def health():
    return {"status": "ok", "agent": root_agent.name}


@app.post("/api/agent", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    user_id = "user"

    if not check_rate_limit(session_id):
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Max {RATE_LIMIT_REQUESTS} messages per 10 minutes.",
        )

    clean_message = sanitize_input(request.message)

    try:
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        session = None

    if session is None:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=clean_message)],
    )

    response_text = ""
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    response_text = "".join(
                        part.text for part in event.content.parts if hasattr(part, "text") and part.text
                    )
                break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    if not response_text:
        response_text = "I didn't get a response. Please try again."

    return ChatResponse(response=response_text, session_id=session_id)


# Vercel serverless handler
from mangum import Mangum
handler = Mangum(app)
