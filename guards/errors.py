"""Turn internal exceptions into safe, friendly client responses.

Clients never see exception text: it can contain provider error bodies, file paths or
library internals. The real cause is logged server-side by exception type and status code only.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from google.genai import errors as genai_errors

from guards.quota import DAILY_QUOTA_MESSAGE, quota_day_window

logger = logging.getLogger("shred_tech.api")

# A 429 from Gemini can be a per-minute limit or the daily quota, and not every 429 says which.
# We only claim "daily" (and the reset time) when the error names a per-day quota. Only that case
# gets a Retry-After: Google documents the reset as midnight Pacific time, so the wait is known. For
# any other 429 we do not know how long to wait, so we send no Retry-After rather than invent one.
RATE_LIMIT_MESSAGE = (
    "SHRED TECH is hitting its free-tier rate limit right now. Please try again in a minute."
)
TIMEOUT_MESSAGE = "That took too long to answer. Please try again."
GENERIC_MESSAGE = "Something went wrong on our end. Please try again."


@dataclass(frozen=True)
class SafeError:
    status_code: int
    detail: str
    retry_after: int | None = None


def _causes(exc: BaseException):
    """Yield exc and everything it was raised from (ADK may wrap provider errors)."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def _is_daily_quota(error: genai_errors.APIError) -> bool:
    """True if the provider's error details name a per-day quota (e.g. a quotaId containing PerDay)."""
    return "perday" in str(getattr(error, "details", "")).lower()


def classify_error(exc: BaseException) -> SafeError:
    """Map any exception to a status code and a message that is safe to show users."""
    for cause in _causes(exc):
        if isinstance(cause, (asyncio.TimeoutError, TimeoutError)):
            return SafeError(504, TIMEOUT_MESSAGE)
        if isinstance(cause, genai_errors.APIError):
            status = getattr(cause, "status", "") or ""
            if cause.code == 429 or status == "RESOURCE_EXHAUSTED":
                if _is_daily_quota(cause):
                    seconds_to_reset = quota_day_window(time.time())[1]
                    return SafeError(503, DAILY_QUOTA_MESSAGE, retry_after=seconds_to_reset)
                return SafeError(503, RATE_LIMIT_MESSAGE)
    return SafeError(500, GENERIC_MESSAGE)


def log_exception(exc: BaseException) -> None:
    """Log what failed without logging the message (which may hold sensitive details)."""
    code = next(
        (c.code for c in _causes(exc) if isinstance(c, genai_errors.APIError)), None
    )
    logger.error("request failed: %s (provider status code: %s)", type(exc).__name__, code)
