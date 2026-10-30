"""Guards the test setup itself: a developer's .env or shell must never change a test's result."""

import os

import dotenv

import api.main  # noqa: F401  (importing the app is what used to pull in .env)
from guards import is_local_dev


def test_importing_the_app_does_not_enable_local_dev():
    assert "SHRED_LOCAL_DEV" not in os.environ
    assert not is_local_dev()


def test_tests_never_see_a_real_api_key():
    assert os.environ["GEMINI_API_KEY"] == "test-key-not-real"


def test_load_dotenv_cannot_read_a_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("SHRED_LOCAL_DEV=1\nLOG_USER_TEXT=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHRED_LOCAL_DEV", raising=False)
    monkeypatch.delenv("LOG_USER_TEXT", raising=False)
    dotenv.load_dotenv()
    assert "SHRED_LOCAL_DEV" not in os.environ and "LOG_USER_TEXT" not in os.environ
