from __future__ import annotations

from ios_restore.infrastructure.logging_setup import redact_secrets


def test_redacts_password_flag() -> None:
    text = "ipatool auth login --password supersecret --email a@b.c"
    redacted = redact_secrets(text)
    assert "supersecret" not in redacted
    assert "--password=***" in redacted


def test_redacts_keychain_passphrase() -> None:
    text = "tool --keychain-passphrase=my-pass-phrase download"
    assert "my-pass-phrase" not in redact_secrets(text)


def test_redacts_assignment_form() -> None:
    text = "password=hunter2 token=abc123"
    redacted = redact_secrets(text)
    assert "hunter2" not in redacted
    assert "abc123" not in redacted
