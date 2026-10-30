"""CORS origin allow-list.

CORS is a *browser* rule: it stops other websites' JavaScript from reading our API responses in a
visitor's browser. It does NOT stop curl, scripts or bots (they ignore CORS), which is why the rate
limits exist. Even so, there is no reason to let every website call the API from a browser.
"""

import os

FRONTEND_ORIGIN = "https://shred-tech.vercel.app"
LOCAL_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def allowed_origins() -> list[str]:
    """The real frontend, plus the Vite dev server only when not running on Vercel."""
    if os.environ.get("VERCEL"):
        return [FRONTEND_ORIGIN]
    return [FRONTEND_ORIGIN, *LOCAL_DEV_ORIGINS]
