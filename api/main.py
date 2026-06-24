import os
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

load_dotenv()

from agent.runner_utils import runner, session_service, APP_NAME, INITIAL_STATE, run_query

# Rate limiting: max requests per window per session
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes
_rate_limit_store: dict[str, deque] = defaultdict(deque)

MAX_MESSAGE_LENGTH = 2000


def check_rate_limit(session_id: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _rate_limit_store[session_id]
    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return False
    timestamps.append(now)
    return True


def sanitize_input(text: str) -> str:
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
    return {"status": "ok", "agent": runner.agent.name}


@app.post("/api/agent", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    if not check_rate_limit(session_id):
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Max {RATE_LIMIT_REQUESTS} messages per 10 minutes.",
        )

    clean_message = sanitize_input(request.message)

    try:
        response_text, _ = await run_query(
            message=clean_message,
            user_id="user",
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    if not response_text:
        response_text = "I didn't get a response. Please try again."

    return ChatResponse(response=response_text, session_id=session_id)


# Vercel serverless handler
from mangum import Mangum
handler = Mangum(app)
