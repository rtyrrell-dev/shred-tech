"""Numbers and claims in the docs must match the code, so they cannot quietly drift apart."""

import pathlib

from guards.quota import DEFAULT_DAILY_QUOTA, DEFAULT_QUOTA_SAFETY, MAX_CALLS_PER_TURN, daily_request_budget

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = {name: (ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "SECURITY.md", ".env.example")}


def test_default_budget_numbers_are_what_the_docs_say():
    assert (DEFAULT_DAILY_QUOTA, float(DEFAULT_QUOTA_SAFETY), daily_request_budget()) == (20, 0.9, 18)
    assert MAX_CALLS_PER_TURN == 4
    for name in ("README.md", "SECURITY.md"):
        assert "18" in DOCS[name], f"{name} no longer mentions the 18-request default budget"


def test_removed_settings_are_gone_from_the_docs():
    for name, text in DOCS.items():
        assert "GLOBAL_DAILY_LIMIT" not in text, f"{name} still documents GLOBAL_DAILY_LIMIT"
    for name in ("README.md", "SECURITY.md"):
        assert "per IP per day" not in DOCS[name] and "per visitor" not in DOCS[name].lower().replace("per-visitor", "")


def test_new_settings_are_documented_everywhere_they_belong():
    for name, text in DOCS.items():
        assert "GEMINI_QUOTA_SAFETY" in text and "GEMINI_DAILY_QUOTA" in text, name


def test_docs_state_the_reset_time_the_code_uses():
    for name in ("README.md", "SECURITY.md"):
        assert "midnight Pacific time" in DOCS[name]


def test_security_md_lists_the_shared_budget_accepted_risk_and_its_impact():
    text = DOCS["SECURITY.md"]
    assert "single visitor or bot can consume the whole shared daily budget" in text
    assert "Demo downtime only" in text


def test_readme_warns_the_demo_may_be_unavailable_late_in_the_day():
    assert "may be unavailable late in the day" in DOCS["README.md"]


def test_both_documents_say_conversation_state_may_reset():
    for name in ("README.md", "SECURITY.md"):
        assert "Conversation state may reset between requests" in DOCS[name] or "conversation state may reset between requests" in DOCS[name].lower(), name
