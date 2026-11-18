"""App Store adapter via ipatool CLI.

On Windows, headless `--keychain-passphrase` often fails with
"item could not be found in the keyring" even when interactive console login
succeeded. Auth/download are therefore launched in a real console where
ipatool prompts for the passphrase itself (same path as a working login).
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import AppReference, PackageInfo
from ios_restore.infrastructure.package_inspector import PackageInspector
from ios_restore.infrastructure.paths import default_tools_dir, resolve_tool

logger = logging.getLogger("ios_restore.appstore")


class AppStoreCliAdapter:
    def __init__(
        self,
        tools_dir: Path | None = None,
        inspector: PackageInspector | None = None,
    ) -> None:
        self._tools_dir = tools_dir or default_tools_dir()
        self._inspector = inspector or PackageInspector()

    def _ipatool(self) -> Path:
        path = resolve_tool("ipatool", self._tools_dir)
        if not path.is_file():
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                "ipatool.exe не найден. Положите бинарник в каталог tools.",
                details=str(path),
            )
        return path

    def _open_console(self, ipatool_args: list[str]) -> None:
        ipatool = self._ipatool()
        # Build a cmd.exe line that keeps the window open after the command.
        # Passphrase is typed interactively in that console — never from our GUI argv.
        inner = subprocess.list2cmdline([str(ipatool), *ipatool_args])
        logger.info("Opening interactive ipatool console: %s", " ".join(ipatool_args))
        if sys.platform == "win32":
            cmdline = f'{inner} & echo. & echo ===== DONE exit=%ERRORLEVEL% ===== & pause'
            try:
                subprocess.Popen(  # noqa: S603
                    ["cmd.exe", "/k", cmdline],
                    cwd=str(self._tools_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
                )
            except OSError as exc:
                raise RestoreError(
                    ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                    "Не удалось открыть окно ipatool.",
                    details=str(exc),
                ) from exc
            return
        raise RestoreError(
            ErrorCode.UNKNOWN_EXTERNAL_ERROR,
            "Интерактивная консоль ipatool сейчас поддерживается на Windows.",
        )

    def begin_interactive_login(self) -> None:
        self._open_console(["auth", "login"])

    def begin_interactive_auth_info(self) -> None:
        # Banner first so it is not confused with auth login.
        self._open_console_with_banner(
            ["auth", "info"],
            banner=(
                "AUTH INFO ONLY: when asked, enter Keychain passphrase "
                "(NOT Apple ID password, NO 2FA)."
            ),
        )

    def _open_console_with_banner(self, ipatool_args: list[str], *, banner: str) -> None:
        ipatool = self._ipatool()
        inner = subprocess.list2cmdline([str(ipatool), *ipatool_args])
        if sys.platform != "win32":
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Интерактивная консоль ipatool сейчас поддерживается на Windows.",
            )
        # Escape carets minimally; banner is our constant ASCII text.
        cmdline = (
            f"echo {banner} & echo. & {inner} "
            f"& echo. & echo ===== DONE exit=%ERRORLEVEL% ===== & pause"
        )
        logger.info("Opening interactive ipatool console: %s", " ".join(ipatool_args))
        try:
            subprocess.Popen(  # noqa: S603
                ["cmd.exe", "/k", cmdline],
                cwd=str(self._tools_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
            )
        except OSError as exc:
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Не удалось открыть окно ipatool.",
                details=str(exc),
            ) from exc

    def begin_interactive_revoke(self) -> None:
        self._open_console(["auth", "revoke"])

    def begin_interactive_download(self, app: AppReference, destination_dir: str) -> Path:
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        args = ["download", "-o", str(dest)]
        if app.bundle_id:
            args.extend(["--bundle-identifier", app.bundle_id])
        elif app.store_id:
            args.extend(["--app-id", app.store_id])
        else:
            raise RestoreError(
                ErrorCode.APP_UNAVAILABLE,
                "Нужен bundle_id или store_id приложения.",
            )
        self._open_console(args)
        return dest

    def wait_for_new_ipa(
        self,
        destination_dir: str | Path,
        *,
        before_names: set[str],
        timeout_sec: float = 2.0,
    ) -> PackageInfo | None:
        """Pick up an IPA that appeared after an interactive download console."""
        dest = Path(destination_dir)
        deadline = time.time() + timeout_sec
        latest: Path | None = None
        while time.time() < deadline:
            candidates = [
                p
                for p in dest.glob("*.ipa")
                if p.name not in before_names and p.is_file()
            ]
            if candidates:
                latest = max(candidates, key=lambda p: p.stat().st_mtime)
                break
            time.sleep(0.2)
        if latest is None:
            # Fallback: newest ipa in folder (user may overwrite same name)
            all_ipas = list(dest.glob("*.ipa"))
            if not all_ipas:
                return None
            latest = max(all_ipas, key=lambda p: p.stat().st_mtime)
        return self.inspect_package(latest)

    def list_ipa_names(self, destination_dir: str | Path) -> set[str]:
        dest = Path(destination_dir)
        if not dest.is_dir():
            return set()
        return {p.name for p in dest.glob("*.ipa")}

    def inspect_package(self, path: Path) -> PackageInfo:
        try:
            return self._inspector.inspect(str(path))
        except RestoreError:
            data = path.read_bytes()
            return PackageInfo(
                local_path=str(path.resolve()),
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                bundle_id=None,
                version=None,
                minimum_os_version=None,
            )

    def session_files_present(self) -> bool:
        root = Path.home() / ".ipatool"
        account = root / "account"
        cookies = root / "cookies"
        return account.is_file() and account.stat().st_size > 10 and cookies.is_file()

    # --- helpers kept for tests / parsing ---

    @staticmethod
    def _parse_json_blob(text: str) -> dict | None:
        text = (text or "").strip()
        if not text:
            return None
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
        return None
