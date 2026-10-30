import json
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

import api.main as main
from guards.cors import FRONTEND_ORIGIN, allowed_origins

ROOT = pathlib.Path(__file__).resolve().parent.parent
API_ORIGIN = "https://shred-tech-api.vercel.app"


def _headers(path: str) -> dict[str, str]:
    config = json.loads((ROOT / path).read_text(encoding="utf-8"))
    rule = next(r for r in config["headers"] if r["source"] == "/(.*)")
    return {h["key"]: h["value"] for h in rule["headers"]}


# --- CORS ------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(main.app)


def _preflight(client, origin):
    return client.options(
        "/api/agent",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_real_frontend_origin_is_allowed(client):
    res = _preflight(client, FRONTEND_ORIGIN)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_other_origins_get_no_cors_grant(client):
    res = _preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in res.headers


def test_credentials_are_not_allowed(client):
    res = _preflight(client, FRONTEND_ORIGIN)
    assert "access-control-allow-credentials" not in res.headers


def test_wildcard_origin_is_never_configured():
    assert "*" not in allowed_origins()


def test_localhost_only_allowed_off_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert allowed_origins() == [FRONTEND_ORIGIN]
    monkeypatch.delenv("VERCEL")
    assert "http://localhost:5173" in allowed_origins()


# --- Security headers in vercel.json ---------------------------------------

@pytest.mark.parametrize("path", ["vercel.json", "frontend/vercel.json"])
def test_baseline_headers_present(path):
    headers = _headers(path)
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Referrer-Policy" in headers
    assert "Strict-Transport-Security" in headers


def test_frontend_csp_is_strict_and_scoped_to_the_api():
    csp = _headers("frontend/vercel.json")["Content-Security-Policy"]
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "script-src 'self'" in csp
    assert f"connect-src 'self' {API_ORIGIN}" in csp
    assert "object-src 'none'" in csp and "base-uri 'self'" in csp


def test_api_responses_are_never_cached_or_framed():
    headers = _headers("vercel.json")
    assert headers["Cache-Control"] == "no-store"
    assert headers["Content-Security-Policy"].startswith("default-src 'none'")


def test_index_html_has_no_inline_scripts():
    # A strict script-src would block them; this also keeps the CSP free of 'unsafe-inline'.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)


# --- Model output rendering ------------------------------------------------

def test_frontend_never_renders_html_from_model_output():
    banned = re.compile(r"dangerouslySetInnerHTML|\.innerHTML|insertAdjacentHTML|document\.write")
    for source in (ROOT / "frontend" / "src").rglob("*.ts*"):
        assert not banned.search(source.read_text(encoding="utf-8")), f"{source.name} injects raw HTML"
