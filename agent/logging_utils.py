"""
Structured JSONL logging for SHRED TECH agent turns.

One JSON object per line is appended to logs/agentops.jsonl after every
run_query call. Logging is purely observational — this module reads event
data only and never writes to session state.

Standard library only: json, os, time, datetime.
"""

import json
import os
import time
from datetime import datetime, timezone

# Resolve logs/ relative to the project root (two levels up from agent/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "agentops.jsonl")

_RESPONSE_PREVIEW_CHARS = 200
_TOOL_RESPONSE_MAX_CHARS = 500


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [{len(text) - max_chars} chars truncated]"


class TurnLogger:
    """Accumulates structured data from one run_async turn, then flushes to JSONL.

    Usage:
        logger = TurnLogger(session_id=sid, user_message=msg)
        async for event in runner.run_async(...):
            logger.observe(event)   # read-only
            # ... existing collection logic unchanged ...
        logger.flush()
    """

    def __init__(self, session_id: str, user_message: str) -> None:
        self._session_id = session_id
        self._user_message = user_message
        self._start_ms = time.monotonic() * 1000

        self._invocation_id: str | None = None
        self._agents_seen: list[str] = []
        self._transfers: list[dict] = []
        self._tool_calls: list[dict] = []
        self._tool_results: list[dict] = []
        self._state_changes: list[dict] = []
        self._final_response_preview: str = ""
        self._latency_ms: int = 0

    def observe(self, event) -> None:
        """Extract logging data from one event. Never writes session state."""
        # ── Invocation ID ───────────────────────────────────────────────────
        inv_id = getattr(event, "invocation_id", None)
        if inv_id and not self._invocation_id:
            self._invocation_id = str(inv_id)

        # ── Author tracking ──────────────────────────────────────────────────
        author = getattr(event, "author", None) or "unknown"
        if author not in self._agents_seen:
            self._agents_seen.append(author)

        # ── Content parts: function calls and responses ──────────────────────
        content = getattr(event, "content", None)
        parts = list(getattr(content, "parts", None) or []) if content else []

        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc:
                fc_name = getattr(fc, "name", "") or ""
                fc_args = dict(getattr(fc, "args", {}) or {})
                # transfer_to_agent is captured via actions below; skip here
                if fc_name and fc_name != "transfer_to_agent":
                    self._tool_calls.append({
                        "agent": author,
                        "tool": fc_name,
                        "args": fc_args,
                    })

            fr = getattr(part, "function_response", None)
            if fr:
                fr_name = getattr(fr, "name", "") or ""
                fr_resp = getattr(fr, "response", {}) or {}
                if fr_name:
                    self._tool_results.append({
                        "tool": fr_name,
                        "response_summary": _truncate(
                            str(fr_resp), _TOOL_RESPONSE_MAX_CHARS
                        ),
                    })

        # ── Actions: transfers and state delta ───────────────────────────────
        actions = getattr(event, "actions", None)
        if actions:
            transfer_target = getattr(actions, "transfer_to_agent", None)
            if transfer_target:
                self._transfers.append({
                    "from_agent": author,
                    "to_agent": str(transfer_target),
                })

            state_delta = getattr(actions, "state_delta", None)
            if state_delta:
                # state_delta is a dict of the keys that changed this event
                self._state_changes.append(dict(state_delta))

        # ── Final response: preview and latency ──────────────────────────────
        if event.is_final_response():
            self._latency_ms = int(time.monotonic() * 1000 - self._start_ms)
            if parts:
                text = "".join(
                    p.text for p in parts if hasattr(p, "text") and p.text
                )
                if text:
                    self._final_response_preview = _truncate(
                        text.strip(), _RESPONSE_PREVIEW_CHARS
                    )

    def flush(self) -> None:
        """Append one JSONL record to logs/agentops.jsonl.

        Failures are silently swallowed — logging must never break the request path.
        """
        record = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "session_id": self._session_id,
            "invocation_id": self._invocation_id or "unknown",
            "user_message": self._user_message,
            "agents_involved": self._agents_seen,
            "transfers": self._transfers,
            "tool_calls": self._tool_calls,
            "tool_results": self._tool_results,
            "state_changes": self._state_changes,
            "latency_ms": self._latency_ms,
            "final_response_preview": self._final_response_preview,
        }
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass
