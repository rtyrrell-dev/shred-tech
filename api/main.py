import asyncio
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

load_dotenv()

from agent.runner_utils import resolve_session_id, run_query, runner
from guards.abuse import INJECTION_REPLY, filter_output, looks_like_injection
from guards.cors import allowed_origins
from guards.errors import classify_error, log_exception
from guards.limits import BodySizeLimitMiddleware
from guards.ratelimit import (
    UNAVAILABLE_MESSAGE,
    Guard,
    GuardUnavailable,
    LimitExceeded,
    build_store_from_env,
    client_ip,
)

# Per-IP, global and per-session limits live in guards/ratelimit.py (Redis-backed, fail-closed).
guard = Guard(store=build_store_from_env())

MAX_MESSAGE_LENGTH = 2000

# Hard ceiling on one model call (coordinator + specialist + tools). Without it, a slow or
# hung provider call would hold a serverless invocation (and its bill) open.
REQUEST_TIMEOUT_SECONDS = 25


def sanitize_input(text: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


# Interactive docs and the OpenAPI schema are disabled: they advertise the API surface to scanners.
app = FastAPI(
    title="SHRED TECH API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(BodySizeLimitMiddleware)

# Only our own frontend may call this from a browser. No cookies are used, so credentials stay off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
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
async def chat(request: ChatRequest, http_request: Request):
    ip = client_ip(http_request.headers, http_request.client.host if http_request.client else None)
    # Server-issued: an id this instance does not know is replaced, not rejected (see runner_utils).
    session_id = await resolve_session_id(request.session_id)
    try:
        await guard.check_request(ip, session_id)
    except LimitExceeded as limit:
        raise HTTPException(
            status_code=limit.status_code,
            detail=limit.message,
            headers={"Retry-After": str(limit.retry_after)},
        ) from None
    except GuardUnavailable:
        raise HTTPException(
            status_code=503, detail=UNAVAILABLE_MESSAGE, headers={"Retry-After": "30"}
        ) from None

    clean_message = sanitize_input(request.message)

    # Obvious prompt-injection / prompt-extraction attempts are answered without a model call, so a
    # blocked message costs no Gemini quota.
    if looks_like_injection(clean_message):
        return ChatResponse(response=INJECTION_REPLY, session_id=session_id)

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            response_text, _ = await run_query(
                message=clean_message,
                user_id="user",
                session_id=session_id,
            )
    except Exception as exc:
        log_exception(exc)
        safe = classify_error(exc)
        headers = {"Retry-After": str(safe.retry_after)} if safe.retry_after else None
        raise HTTPException(
            status_code=safe.status_code, detail=safe.detail, headers=headers
        ) from None

    if not response_text:
        response_text = "I didn't get a response. Please try again."

    return ChatResponse(response=filter_output(response_text), session_id=session_id)


# Vercel serverless handler
from mangum import Mangum
handler = Mangum(app)
