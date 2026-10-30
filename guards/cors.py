"""CORS origin allow-list.

CORS is a *browser* rule: it stops other websites' JavaScript from reading our API responses in a
visitor's browser. It does NOT stop curl, scripts or bots (they ignore CORS), which is why the rate
limits exist. Even so, there is no reason to let every website call the API from a browser.
"""

from guards import is_local_dev

FRONTEND_ORIGIN = "https://shred-tech.vercel.app"
LOCAL_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def allowed_origins() -> list[str]:
    """The real frontend, plus the Vite dev server only in explicit local dev (SHRED_LOCAL_DEV=1)."""
    if is_local_dev():
        return [FRONTEND_ORIGIN, *LOCAL_DEV_ORIGINS]
    return [FRONTEND_ORIGIN]
