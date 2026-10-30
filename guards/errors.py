"""Turn internal exceptions into safe, friendly client responses.

Clients never see exception text: it can contain provider error bodies, file paths or
library internals. The real cause is logged server-side by exception type and status code only.
"""

import asyncio
import logging
from dataclasses import dataclass

from google.genai import errors as genai_errors

logger = logging.getLogger("shred_tech.api")

QUOTA_MESSAGE = (
    "SHRED TECH is at capacity right now. Please try again in a little while."
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


def classify_error(exc: BaseException) -> SafeError:
    """Map any exception to a status code and a message that is safe to show users."""
    for cause in _causes(exc):
        if isinstance(cause, (asyncio.TimeoutError, TimeoutError)):
            return SafeError(504, TIMEOUT_MESSAGE)
        if isinstance(cause, genai_errors.APIError):
            status = getattr(cause, "status", "") or ""
            if cause.code == 429 or status == "RESOURCE_EXHAUSTED":
                return SafeError(503, QUOTA_MESSAGE, retry_after=60)
    return SafeError(500, GENERIC_MESSAGE)


def log_exception(exc: BaseException) -> None:
    """Log what failed without logging the message (which may hold sensitive details)."""
    code = next(
        (c.code for c in _causes(exc) if isinstance(c, genai_errors.APIError)), None
    )
    logger.error("request failed: %s (provider status code: %s)", type(exc).__name__, code)
