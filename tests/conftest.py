"""Test environment: no real credentials or network are ever needed."""

import os

# The ADK client reads this at import time; tests mock every model call.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
# Keep tests independent of any developer .env or deployed configuration.
for _name in ("VERCEL", "SHRED_LOCAL_DEV"):
    os.environ.pop(_name, None)

