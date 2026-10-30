"""The app needs no Redis, Upstash or Vercel KV: it must start and answer with none of them configured."""

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Runs in a fresh interpreter so the app is imported exactly as a cold serverless instance would,
# with the model call replaced so no key or network is needed.
SCRIPT = """
import json, sys
sys.path.insert(0, {root!r})
from fastapi.testclient import TestClient
import api.main as main

async def fake_run_query(**kwargs):
    return "Here is the answer.", "SetupAgent"

main.run_query = fake_run_query
client = TestClient(main.app)
health = client.get("/health")
chat = client.post("/api/agent", json={{"message": "My strat buzzes on the low E"}})
print(json.dumps({{
    "health": health.status_code,
    "chat": chat.status_code,
    "reply": chat.json().get("response"),
    "session_id": chat.json().get("session_id"),
    "store_modules": sorted(m for m in sys.modules if m.split(".")[0] in ("upstash_redis", "redis", "fakeredis")),
}}))
"""

STORE_VARIABLES = (
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "KV_REST_API_URL",
    "KV_REST_API_TOKEN",
    "KV_URL",
    "REDIS_URL",
    "SHRED_LOCAL_DEV",
    "VERCEL",
)


def test_app_starts_and_serves_a_chat_request_with_no_store_configured():
    env = {k: v for k, v in os.environ.items() if k not in STORE_VARIABLES}
    env["GEMINI_API_KEY"] = "test-key-not-real"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(  # noqa: S603 - fixed argv: this interpreter and a script defined above
        [sys.executable, "-c", SCRIPT.format(root=str(ROOT))],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["health"] == 200
    assert out["chat"] == 200
    assert out["reply"] == "Here is the answer."
    assert out["session_id"]
    assert out["store_modules"] == []  # nothing imported a Redis client


def test_no_source_file_depends_on_a_redis_client():
    banned = ("upstash", "redis", "KV_REST")
    for folder in ("api", "agent", "guards"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word.lower() not in text, f"{path.relative_to(ROOT)} mentions {word}"
