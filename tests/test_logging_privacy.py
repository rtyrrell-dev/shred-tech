import json
import pathlib
import re
from types import SimpleNamespace

import agent.logging_utils as logging_utils
from agent.logging_utils import TurnLogger

SECRET_IN_USER_TEXT = "sk-LIVE-user-pasted-secret-0123456789"
SECRET_IN_TOOL_ARGS = "tool-arg-secret-ZXCV"
USER_MESSAGE = f"my strat buzzes, here is my key {SECRET_IN_USER_TEXT}"


def _event(*, parts=(), actions=None, final=False, author="TroubleshootingAgent"):
    return SimpleNamespace(
        invocation_id="inv-1",
        author=author,
        content=SimpleNamespace(parts=list(parts)),
        actions=actions,
        is_final_response=lambda: final,
    )


def _run_turn(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "agentops.jsonl"
    monkeypatch.setattr(logging_utils, "LOG_DIR", str(log_file.parent))
    monkeypatch.setattr(logging_utils, "LOG_FILE", str(log_file))

    call = SimpleNamespace(name="diagnose_issue", args={"symptom": SECRET_IN_TOOL_ARGS})
    response = SimpleNamespace(name="diagnose_issue", response={"echo": SECRET_IN_TOOL_ARGS})
    logger = TurnLogger(session_id="sess-1", user_message=USER_MESSAGE)
    logger.observe(_event(parts=[SimpleNamespace(function_call=call, function_response=None, text=None)]))
    logger.observe(_event(parts=[SimpleNamespace(function_call=None, function_response=response, text=None)]))
    logger.observe(
        _event(
            actions=SimpleNamespace(
                transfer_to_agent=None, state_delta={"guitar_model": f"Strat {SECRET_IN_USER_TEXT}"}
            )
        )
    )
    logger.observe(
        _event(
            parts=[SimpleNamespace(function_call=None, function_response=None, text=f"Reply repeating {SECRET_IN_USER_TEXT}")],
            final=True,
        )
    )
    logger.flush()
    return log_file.read_text(encoding="utf-8")


def test_default_log_contains_no_user_text_tool_args_or_state_values(tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_USER_TEXT", raising=False)
    raw = _run_turn(tmp_path, monkeypatch)
    for secret in (SECRET_IN_USER_TEXT, SECRET_IN_TOOL_ARGS, "buzzes", "Strat"):
        assert secret not in raw
    record = json.loads(raw)
    assert record["user_message_chars"] == len(USER_MESSAGE)
    assert re.fullmatch(r"[0-9a-f]{12}", record["user_message_sha256_12"])
    assert record["tool_calls"] == [{"agent": "TroubleshootingAgent", "tool": "diagnose_issue"}]
    assert "user_message" not in record and "final_response_preview" not in record


def test_tool_arguments_are_never_logged_even_when_text_logging_is_on(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_USER_TEXT", "1")
    raw = _run_turn(tmp_path, monkeypatch)
    assert SECRET_IN_TOOL_ARGS not in raw
    assert '"args"' not in raw


def test_opt_in_logs_truncated_text(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_USER_TEXT", "1")
    record = json.loads(_run_turn(tmp_path, monkeypatch))
    assert "buzzes" in record["user_message"]
    assert len(record["user_message"]) <= logging_utils._USER_TEXT_MAX_CHARS + 40


def test_log_files_are_not_tracked_by_git():
    gitignore = pathlib.Path(__file__).resolve().parent.parent / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    assert "logs/" in lines and ".env" in lines
