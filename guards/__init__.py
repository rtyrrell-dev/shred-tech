"""Abuse-protection helpers for the SHRED TECH API (errors, limits, rate limiting)."""

import os


def is_local_dev() -> bool:
    """True only when SHRED_LOCAL_DEV=1 is set explicitly (in a developer's own .env).

    Production-safe behaviour is the DEFAULT: Redis required (fail closed), Vercel's client-IP
    headers trusted, localhost CORS origins off. We deliberately do not detect "am I on Vercel?"
    from the VERCEL variable: Vercel only exposes it when a project setting is enabled, and a
    missing variable must never silently relax protection.
    """
    return os.environ.get("SHRED_LOCAL_DEV", "").strip() == "1"
