"""Numbers and claims in the docs must match the code, so they cannot quietly drift apart."""

import pathlib

from guards.quota import MAX_CALLS_PER_TURN

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = {name: (ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "SECURITY.md", ".env.example")}


def test_per_turn_cap_is_what_the_docs_say():
    assert MAX_CALLS_PER_TURN == 4


REMOVED_SETTINGS = (
    "GLOBAL_DAILY_LIMIT",
    "GEMINI_DAILY_QUOTA",
    "GEMINI_QUOTA_SAFETY",
    "UPSTASH_",
    "KV_REST_API",
)


def test_removed_settings_are_gone_from_the_docs():
    for name, text in DOCS.items():
        for setting in REMOVED_SETTINGS:
            assert setting not in text, f"{name} still documents {setting}"
    for name in ("README.md", "SECURITY.md"):
        assert "per IP per day" not in DOCS[name] and "per visitor" not in DOCS[name].lower().replace("per-visitor", "")


def test_docs_state_the_reset_time_the_code_uses():
    for name in ("README.md", "SECURITY.md"):
        assert "midnight Pacific time" in DOCS[name]


def test_both_documents_say_conversation_state_may_reset():
    for name in ("README.md", "SECURITY.md"):
        assert "Conversation state may reset between requests" in DOCS[name] or "conversation state may reset between requests" in DOCS[name].lower(), name
