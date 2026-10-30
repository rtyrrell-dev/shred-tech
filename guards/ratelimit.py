"""Store-backed rate limiting and server-issued sessions.

Why a store: Vercel runs the API as stateless serverless functions. Each invocation may land on a
different instance (or a fresh one), so counters kept in Python memory reset constantly and are not
shared. The counters therefore live in Redis (Upstash), which every instance talks to.

How counting works (fixed windows): the current time window is part of the key name, e.g.
``rl:ip:1.2.3.4:min:29481234``. INCR returns how many requests this window has seen. When the
window rolls over the key name changes, so old counts simply stop mattering. EXPIRE is only for
cleanup, so a missed EXPIRE can never block anyone forever.

Fail closed: if the store is down or not configured on Vercel, requests are refused with a friendly
503 instead of being allowed through unmetered. Cost protection must not silently turn off.
"""

import asyncio
import ipaddress
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol

from guards import is_local_dev
from guards.quota import global_daily_turn_limit

logger = logging.getLogger("shred_tech.guard")

# --- Limits (tune for your Gemini quota; the global cap is the real budget guard) ---------------
IP_PER_MINUTE = 10
IP_PER_DAY = 100
# The global daily limit is derived from the Gemini free-tier quota (see guards/quota.py).
SESSION_MAX_MESSAGES = 30
SESSION_TTL_SECONDS = 24 * 60 * 60
STORE_TIMEOUT_SECONDS = 2.0

MINUTE = 60
DAY = 24 * 60 * 60


class LimitExceeded(Exception):
    """The caller is over a limit. Carries a friendly message and an HTTP status."""

    def __init__(self, message: str, retry_after: int, status_code: int = 429) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.status_code = status_code


class GuardUnavailable(Exception):
    """The limiter store is unreachable or unconfigured, so we fail closed."""


UNAVAILABLE_MESSAGE = "SHRED TECH is temporarily unavailable. Please try again shortly."


class Store(Protocol):
    async def incr_window(self, key: str, ttl: int) -> int: ...
    async def exists(self, key: str) -> bool: ...
    async def set_with_ttl(self, key: str, ttl: int) -> None: ...


class MemoryStore:
    """Process-local store for local development and tests. NOT valid for serverless production."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._data: dict[str, tuple[int, float]] = {}

    def _live(self, key: str):
        entry = self._data.get(key)
        if entry and entry[1] > self._clock():
            return entry
        self._data.pop(key, None)
        return None

    async def incr_window(self, key: str, ttl: int) -> int:
        entry = self._live(key)
        count = (entry[0] if entry else 0) + 1
        self._data[key] = (count, entry[1] if entry else self._clock() + ttl)
        return count

    async def exists(self, key: str) -> bool:
        return self._live(key) is not None

    async def set_with_ttl(self, key: str, ttl: int) -> None:
        self._data[key] = (1, self._clock() + ttl)


class UpstashStore:
    """Redis over Upstash's REST API (``upstash-redis``), async client."""

    def __init__(self, redis) -> None:
        self._redis = redis

    async def incr_window(self, key: str, ttl: int) -> int:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl)
        return int(count)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def set_with_ttl(self, key: str, ttl: int) -> None:
        await self._redis.set(key, "1", ex=ttl)


def build_store_from_env() -> Store | None:
    """Upstash store if configured; in-memory only in explicit local dev; otherwise None (fail closed).

    Accepts the Upstash variable names and the legacy Vercel KV names the marketplace may inject.
    """
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    if url and token:
        from upstash_redis.asyncio import Redis

        return UpstashStore(Redis(url=url, token=token, rest_retries=1, rest_retry_interval=0.2))
    if is_local_dev():
        logger.warning("SHRED_LOCAL_DEV=1 and no Upstash credentials: using in-memory limiter")
        return MemoryStore()
    logger.error("rate limit store is not configured; failing closed")
    return None


def client_ip(headers, peer_host: str | None) -> str:
    """Best-effort client IP, normalised for rate-limit keys.

    Behind Vercel, ``x-real-ip`` / ``x-vercel-forwarded-for`` are set by Vercel itself (it overwrites
    X-Forwarded-For too, to stop spoofing), so they are trustworthy. In explicit local dev there is no
    such proxy and a client could send those headers itself, so we ignore them and use the socket peer.

    IPv6 addresses are grouped by /64: a single user typically controls a whole /64, so keying on
    the full address would let them dodge limits by rotating addresses.
    """
    raw = None
    if not is_local_dev():
        raw = headers.get("x-real-ip") or headers.get("x-vercel-forwarded-for")
        if raw:
            raw = raw.split(",")[0].strip()
    raw = raw or peer_host or "unknown"
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return "unknown"
    if isinstance(addr, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{addr}/64", strict=False).network_address)
    return str(addr)


@dataclass
class Guard:
    """Runs every per-request abuse check and issues/validates session ids."""

    store: Store | None
    ip_per_minute: int = IP_PER_MINUTE
    ip_per_day: int = IP_PER_DAY
    global_per_day: int = field(default_factory=global_daily_turn_limit)
    session_max_messages: int = SESSION_MAX_MESSAGES
    clock: Callable[[], float] = time.time

    async def _store_call(self, coro):
        try:
            async with asyncio.timeout(STORE_TIMEOUT_SECONDS):
                return await coro
        except Exception as exc:  # any store failure => fail closed
            logger.error("limiter store error: %s", type(exc).__name__)
            raise GuardUnavailable from exc

    async def _hit(self, name: str, window: int) -> tuple[int, int]:
        """Count one hit in the current window. Returns (count, seconds until window ends)."""
        now = int(self.clock())
        bucket = now // window
        count = await self._store_call(self.store.incr_window(f"rl:{name}:{bucket}", window * 2))
        return count, (bucket + 1) * window - now

    async def check_request(self, ip: str, session_id: str | None) -> str:
        """Enforce all limits for one chat request and return the session id to use.

        Raises LimitExceeded (429/503) or GuardUnavailable (fail closed).
        """
        if self.store is None:
            raise GuardUnavailable

        count, wait = await self._hit(f"ip:{ip}:min", MINUTE)
        if count > self.ip_per_minute:
            raise LimitExceeded(
                "You're sending messages too quickly. Please wait a minute and try again.", wait
            )

        count, wait = await self._hit(f"ip:{ip}:day", DAY)
        if count > self.ip_per_day:
            raise LimitExceeded(
                "You've reached today's message limit. Please come back tomorrow.", wait
            )

        count, wait = await self._hit("global:day", DAY)
        if count > self.global_per_day:
            raise LimitExceeded(
                "SHRED TECH has reached its daily capacity. Please try again tomorrow.",
                wait,
                status_code=503,
            )

        session_id = await self._resolve_session(session_id)

        count = await self._store_call(
            self.store.incr_window(f"sessmsgs:{session_id}", SESSION_TTL_SECONDS)
        )
        if count > self.session_max_messages:
            raise LimitExceeded(
                "This conversation has reached its message limit. "
                "Click \"New session\" to keep going.",
                SESSION_TTL_SECONDS,
            )
        return session_id

    async def _resolve_session(self, claimed: str | None) -> str:
        """Accept only session ids this server issued; otherwise issue a fresh one.

        The client may *claim* an id, but it is only honoured if the id exists in the store. Ids are
        random UUIDs, so they cannot be guessed to join someone else's conversation, and a client
        cannot mint ids to dodge the per-session cap.
        """
        if claimed and await self._store_call(self.store.exists(f"sess:{claimed}")):
            return claimed
        new_id = str(uuid.uuid4())
        await self._store_call(self.store.set_with_ttl(f"sess:{new_id}", SESSION_TTL_SECONDS))
        return new_id
