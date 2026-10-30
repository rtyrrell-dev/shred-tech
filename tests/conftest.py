"""Test environment: no real credentials or network are ever needed."""

import os

# The ADK client reads this at import time; tests mock every model call.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
# Keep tests independent of any developer .env or deployed configuration.
for _name in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "KV_REST_API_URL", "KV_REST_API_TOKEN", "VERCEL", "SHRED_LOCAL_DEV", "GEMINI_DAILY_QUOTA", "GEMINI_QUOTA_SAFETY", "GLOBAL_DAILY_LIMIT"):
    os.environ.pop(_name, None)


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_guard(monkeypatch):
    """Every test gets its own empty in-memory limiter, so tests never share counters."""
    import api.main as main
    from guards.ratelimit import Guard, MemoryStore

    # Generous limits so unrelated tests are never throttled; limit tests build their own Guard.
    guard = Guard(store=MemoryStore(), ip_per_minute=10_000, budget_cap=10_000)
    monkeypatch.setattr(main, "guard", guard)
