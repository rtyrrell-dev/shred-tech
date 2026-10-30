import asyncio
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

load_dotenv()

from agent.runner_utils import run_query, runner
from guards.abuse import INJECTION_REPLY, filter_output, looks_like_injection
from guards.budget import BudgetExhausted, TurnState
from guards.cors import allowed_origins
from guards.errors import classify_error, log_exception
from guards.quota import DAILY_QUOTA_MESSAGE
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


def _budget_spent(spent: BudgetExhausted) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=DAILY_QUOTA_MESSAGE,
        headers={"Retry-After": str(spent.retry_after)},
    )


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE, headers={"Retry-After": "30"})


@app.post("/api/agent", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    ip = client_ip(http_request.headers, http_request.client.host if http_request.client else None)
    try:
        session_id = await guard.check_request(ip, request.session_id)
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

    # Obvious prompt-injection / prompt-extraction attempts are answered without a model call. This
    # runs before any budget accounting, so a blocked message costs the shared budget nothing.
    if looks_like_injection(clean_message):
        return ChatResponse(response=INJECTION_REPLY, session_id=session_id)

    # Admission check: if the shared daily budget is already spent, refuse now without touching ADK.
    try:
        await guard.budget.require_available()
    except BudgetExhausted as spent:
        raise _budget_spent(spent) from None
    except GuardUnavailable:
        raise _unavailable() from None

    turn = TurnState(budget=guard.budget)
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            response_text, _ = await run_query(
                message=clean_message,
                user_id="user",
                session_id=session_id,
                turn=turn,
            )
    except Exception as exc:
        # If the budget ended mid-turn, that is the real story; report it instead of the side effect.
        if turn.exhausted is not None:
            raise _budget_spent(turn.exhausted) from None
        if turn.unavailable:
            raise _unavailable() from None
        log_exception(exc)
        safe = classify_error(exc)
        headers = {"Retry-After": str(safe.retry_after)} if safe.retry_after else None
        raise HTTPException(
            status_code=safe.status_code, detail=safe.detail, headers=headers
        ) from None

    # The budget ran out part-way through this turn (for example after the coordinator's call but
    # before the specialist's): the plugin replaced the refused call with a friendly message.
    if turn.exhausted is not None:
        raise _budget_spent(turn.exhausted)
    if turn.unavailable:
        raise _unavailable()

    if not response_text:
        response_text = "I didn't get a response. Please try again."

    return ChatResponse(response=filter_output(response_text), session_id=session_id)


# Vercel serverless handler
from mangum import Mangum
handler = Mangum(app)
