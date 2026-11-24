"""macOS Terminal launch must stay ASCII-safe and use open -a Terminal."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter


def test_open_macos_terminal_writes_command_and_opens(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "icarcas-test.command"

    def fake_mkstemp(prefix="icarcas-", suffix=".command"):
        fd = os.open(target, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return fd, str(target)

    monkeypatch.setattr("tempfile.mkstemp", fake_mkstemp)
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr="", stdout=""))
    monkeypatch.setattr("subprocess.run", mock_run)

    AppStoreCliAdapter._open_macos_terminal(
        "cd /tmp && echo hi; read -n 1 -s -r -p 'Press any key to close...'"
    )

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[:3] == ["/usr/bin/open", "-a", "Terminal"]
    assert args[3] == str(target)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash\n")
    assert "…" not in text
    assert "Press any key to close..." in text


def test_open_unix_terminal_prompt_is_ascii(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_open(shell_line: str) -> None:
        captured["line"] = shell_line

    monkeypatch.setattr(AppStoreCliAdapter, "_open_macos_terminal", staticmethod(fake_open))
    monkeypatch.setattr(
        "ios_restore.infrastructure.appstore_cli_adapter.sys",
        type("S", (), {"platform": "darwin"})(),
    )

    adapter = AppStoreCliAdapter(tools_dir=Path("/tmp/tools"))
    adapter._open_unix_terminal(["/tmp/tools/ipatool", "auth", "login"])
    assert "…" not in captured["line"]
    assert "Press any key to close..." in captured["line"]
    assert "ipatool" in captured["line"]
