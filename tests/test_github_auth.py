from __future__ import annotations

import os

from lifeplanner_core.github_auth import github_token


def test_direct_lifeplanner_token_has_priority(monkeypatch):
    monkeypatch.setenv("LIFEPLANNER_GITHUB_TOKEN", "lifeplanner-token")
    monkeypatch.setenv("GITHUB_TOKEN", "generic-token")
    assert github_token() == "lifeplanner-token"


def test_secure_token_file(monkeypatch, tmp_path):
    monkeypatch.delenv("LIFEPLANNER_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    token = tmp_path / "github.token"
    token.write_text("read-only-token\n", encoding="utf-8")
    if os.name != "nt":
        token.chmod(0o600)
    monkeypatch.setenv("LIFEPLANNER_GITHUB_TOKEN_FILE", str(token))
    assert github_token() == "read-only-token"


def test_insecure_token_file_is_rejected_on_unix(monkeypatch, tmp_path):
    if os.name == "nt":
        return
    monkeypatch.delenv("LIFEPLANNER_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    token = tmp_path / "github.token"
    token.write_text("secret", encoding="utf-8")
    token.chmod(0o644)
    monkeypatch.setenv("LIFEPLANNER_GITHUB_TOKEN_FILE", str(token))
    assert github_token() == ""


def test_multiline_token_file_is_rejected(monkeypatch, tmp_path):
    monkeypatch.delenv("LIFEPLANNER_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    token = tmp_path / "github.token"
    token.write_text("one\ntwo", encoding="utf-8")
    if os.name != "nt":
        token.chmod(0o600)
    monkeypatch.setenv("LIFEPLANNER_GITHUB_TOKEN_FILE", str(token))
    assert github_token() == ""
