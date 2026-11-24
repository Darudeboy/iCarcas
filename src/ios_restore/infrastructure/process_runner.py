"""Safe subprocess runner for external CLI tools."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.infrastructure.logging_setup import redact_secrets
from ios_restore.infrastructure.paths import macos_brew_bin_dirs

logger = logging.getLogger("ios_restore.process")

DEFAULT_MAX_OUTPUT_BYTES = 256_000
DEFAULT_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATHEXT",
        "COMSPEC",
    }
)


@dataclass(frozen=True, slots=True)
class ProcessResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    cancelled: bool = False


class ProcessRunner:
    """Run external tools with shell=False, timeouts, and secret redaction."""

    def __init__(
        self,
        *,
        env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        popen_factory=subprocess.Popen,
    ) -> None:
        self._env_allowlist = env_allowlist
        self._max_output_bytes = max_output_bytes
        self._popen_factory = popen_factory
        self._lock = threading.Lock()
        self._current_proc: subprocess.Popen[str] | None = None
        self._cancel_requested = False

    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float | None = 120.0,
        cwd: str | Path | None = None,
        extra_env: Mapping[str, str] | None = None,
        check: bool = True,
    ) -> ProcessResult:
        if not args:
            raise ValueError("args must not be empty")
        executable = Path(args[0])
        if not self._is_executable_path_ok(executable):
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                f"Исполняемый файл не найден или недоступен: {executable.name}",
                details=str(executable),
            )

        command = tuple(str(a) for a in args)
        env = self._build_env(extra_env)
        logger.info("Running: %s", redact_secrets(" ".join(command)))

        with self._lock:
            self._cancel_requested = False

        popen_kwargs: dict = {
            "args": list(command),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "shell": False,
            "cwd": str(cwd) if cwd else None,
            "env": env,
        }
        # Avoid black console flashes on Windows when spawning CLI helpers.
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000
            )
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            popen_kwargs["startupinfo"] = startupinfo
        try:
            proc = self._popen_factory(**popen_kwargs)
        except FileNotFoundError as exc:
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                f"Инструмент не найден: {executable.name}",
                details=str(exc),
            ) from exc
        except OSError as exc:
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Не удалось запустить внешний процесс.",
                details=str(exc),
            ) from exc

        with self._lock:
            self._current_proc = proc

        timed_out = False
        cancelled = False
        try:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                stdout, stderr = proc.communicate()
            with self._lock:
                cancelled = self._cancel_requested
        finally:
            with self._lock:
                self._current_proc = None

        stdout = self._truncate(stdout or "")
        stderr = self._truncate(stderr or "")
        result = ProcessResult(
            command=command,
            returncode=int(proc.returncode if proc.returncode is not None else -1),
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            cancelled=cancelled,
        )
        self._log_result(result)

        if timed_out:
            raise RestoreError(
                ErrorCode.OPERATION_TIMEOUT,
                "Внешняя команда превысила время ожидания.",
                details=redact_secrets(stderr[:500]),
            )
        if cancelled:
            raise RestoreError(
                ErrorCode.OPERATION_CANCELLED,
                "Операция отменена пользователем.",
            )
        if check and result.returncode != 0:
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Внешняя команда завершилась с ошибкой.",
                details=redact_secrets((stderr or stdout)[:500]),
            )
        return result

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True
            proc = self._current_proc
        if proc and proc.poll() is None:
            proc.kill()

    def _build_env(self, extra_env: Mapping[str, str] | None) -> dict[str, str]:
        env: dict[str, str] = {}
        for key in self._env_allowlist:
            value = os.environ.get(key)
            if value is not None:
                env[key] = value
        if extra_env:
            for key, value in extra_env.items():
                if key in self._env_allowlist:
                    env[key] = value
        # Finder-launched .app often has a PATH without Homebrew.
        if sys.platform == "darwin":
            brew_prefix = os.pathsep.join(str(p) for p in macos_brew_bin_dirs())
            path = env.get("PATH", "")
            env["PATH"] = (
                f"{brew_prefix}{os.pathsep}{path}" if path else brew_prefix
            )
        return env

    def _truncate(self, text: str) -> str:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= self._max_output_bytes:
            return text
        clipped = encoded[: self._max_output_bytes]
        return clipped.decode("utf-8", errors="replace") + "\n…[truncated]"

    def _log_result(self, result: ProcessResult) -> None:
        logger.info(
            "Finished returncode=%s timed_out=%s cancelled=%s",
            result.returncode,
            result.timed_out,
            result.cancelled,
        )
        if result.stdout:
            logger.debug("stdout: %s", redact_secrets(result.stdout[:2000]))
        if result.stderr:
            logger.debug("stderr: %s", redact_secrets(result.stderr[:2000]))

    @staticmethod
    def _is_executable_path_ok(executable: Path) -> bool:
        # Bare command names are resolved by the OS via PATH at spawn time.
        if executable.name == str(executable) and not executable.is_absolute():
            return bool(executable.name)
        return executable.exists() and executable.is_file()
