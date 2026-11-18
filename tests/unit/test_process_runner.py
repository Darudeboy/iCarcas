from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.infrastructure.process_runner import ProcessRunner


class FakeProc:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "ok",
        stderr: str = "",
        hang: bool = False,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._hang = hang
        self._killed = False

    def communicate(self, timeout: float | None = None):
        if self._hang and not self._killed:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout or 0)
        return self._stdout, self._stderr

    def kill(self) -> None:
        self._killed = True
        self.returncode = -9

    def poll(self):
        return None if self._hang and not self._killed else self.returncode


def test_success(tmp_path: Path) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_text("x", encoding="utf-8")

    def factory(*_a, **_k):
        return FakeProc(stdout="hello")

    runner = ProcessRunner(popen_factory=factory)
    result = runner.run([str(exe), "arg"], timeout=1)
    assert result.returncode == 0
    assert result.stdout == "hello"


def test_nonzero_exit(tmp_path: Path) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"x")

    def factory(*_a, **_k):
        return FakeProc(returncode=2, stderr="boom")

    runner = ProcessRunner(popen_factory=factory)
    with pytest.raises(RestoreError) as exc:
        runner.run([str(exe)], timeout=1)
    assert exc.value.code == ErrorCode.UNKNOWN_EXTERNAL_ERROR


def test_timeout(tmp_path: Path) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"x")

    def factory(*_a, **_k):
        return FakeProc(hang=True, stdout="", stderr="slow")

    runner = ProcessRunner(popen_factory=factory)
    with pytest.raises(RestoreError) as exc:
        runner.run([str(exe)], timeout=0.01)
    assert exc.value.code == ErrorCode.OPERATION_TIMEOUT


def test_cancel(tmp_path: Path) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"x")
    holder: dict[str, ProcessRunner] = {}

    class CancellingProc(FakeProc):
        def communicate(self, timeout: float | None = None):
            holder["runner"].cancel()
            return "out", ""

    def factory(*_a, **_k):
        return CancellingProc(returncode=0)

    runner = ProcessRunner(popen_factory=factory)
    holder["runner"] = runner
    with pytest.raises(RestoreError) as exc:
        runner.run([str(exe)], timeout=1)
    assert exc.value.code == ErrorCode.OPERATION_CANCELLED


def test_missing_absolute_tool() -> None:
    runner = ProcessRunner(popen_factory=lambda *_a, **_k: FakeProc())
    with pytest.raises(RestoreError) as exc:
        runner.run([str(Path("C:/definitely/missing/tool.exe"))])
    assert exc.value.code == ErrorCode.TOOL_NOT_FOUND
