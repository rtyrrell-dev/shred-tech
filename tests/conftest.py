"""Test environment: hermetic, so a local run and a CI run behave the same.

No real credentials, network, or developer configuration may influence a test. Three things could:

* the app modules call ``load_dotenv()`` when imported, which would copy a developer's ``.env``
  (for example ``SHRED_LOCAL_DEV=1``) into the environment *after* anything cleared it;
* variables already set in the developer's shell;
* a real API key.

This file runs before any test module imports the app, so it can close all three.
"""

import os

import dotenv

# Make load_dotenv() a no-op for every module that imports it from now on (agent/agent.py,
# agent/runner_utils.py, api/main.py). Tests that need a setting use monkeypatch.setenv.
dotenv.load_dotenv = lambda *args, **kwargs: False

# Never use a real key; every model call in the tests is mocked. Assigned, not setdefault, so a key
# in the developer's shell cannot be picked up either.
os.environ["GEMINI_API_KEY"] = "test-key-not-real"

# Settings that change app behaviour: start from the production-strict defaults.
for _name in ("VERCEL", "SHRED_LOCAL_DEV", "LOG_USER_TEXT"):
    os.environ.pop(_name, None)
