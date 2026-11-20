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
from ios_restore.domain.models import (
    AppReference,
    AppSearchResult,
    AppVersionInfo,
    PackageInfo,
    PurchasedApp,
)
from ios_restore.infrastructure import keychain_passphrase as kc_pass
from ios_restore.infrastructure.package_inspector import PackageInspector
from ios_restore.infrastructure.paths import default_tools_dir, resolve_tool
from ios_restore.infrastructure.process_runner import ProcessRunner

logger = logging.getLogger("ios_restore.appstore")


class AppStoreCliAdapter:
    def __init__(
        self,
        tools_dir: Path | None = None,
        inspector: PackageInspector | None = None,
    ) -> None:
        self._tools_dir = tools_dir or default_tools_dir()
        self._inspector = inspector or PackageInspector()
        self._runner = ProcessRunner()
        self._active_proc: subprocess.Popen[str] | None = None

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
        self._open_console_with_banner(
            ["auth", "info"],
            banner=(
                "ТОЛЬКО ПРОВЕРКА СЕССИИ: введите Keychain passphrase "
                "(НЕ пароль Apple ID, без 2FA)."
            ),
        )

    def auth_info(self) -> dict[str, str]:
        """Headless auth info when passphrase is stored; else raise."""
        passphrase = kc_pass.load_passphrase()
        if not passphrase:
            raise RestoreError(
                ErrorCode.AUTHENTICATION_FAILED,
                "Нет сохранённого Keychain passphrase. "
                "Сохраните его в настройках или нажмите «Проверить сессию…».",
            )
        ipatool = self._ipatool()
        result = self._runner.run(
            [
                str(ipatool),
                "--non-interactive",
                "--keychain-passphrase",
                passphrase,
                "--format",
                "json",
                "auth",
                "info",
            ],
            timeout=60.0,
            cwd=str(self._tools_dir),
            check=False,
        )
        blob = self._parse_json_blob(result.stdout) or self._parse_json_blob(result.stderr)
        if not isinstance(blob, dict):
            raise RestoreError(
                ErrorCode.AUTHENTICATION_FAILED,
                "Не удалось прочитать auth info.",
                details=(result.stdout or result.stderr)[:500],
            )
        out: dict[str, str] = {}
        for key in ("email", "name", "storefront", "success"):
            if key in blob and blob[key] is not None:
                out[key] = str(blob[key])
        return out

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

    def begin_interactive_download(
        self,
        app: AppReference,
        destination_dir: str,
        *,
        try_purchase: bool = False,
        external_version_id: str | None = None,
    ) -> Path:
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
        if external_version_id:
            args.extend(["--external-version-id", external_version_id])
        if try_purchase:
            # Only obtains a license in the *current* storefront when available.
            args.append("--purchase")
        version_note = (
            f" Версия external-version-id={external_version_id}."
            if external_version_id
            else " Последняя доступная версия."
        )
        banner = (
            "ЗАГРУЗКА IPA: введите Keychain passphrase "
            "(НЕ пароль Apple ID)."
            + version_note
            + (
                " Флаг --purchase: лицензия только в текущем регионе витрины."
                if try_purchase
                else " Нужна уже существующая лицензия на этом Apple ID."
            )
        )
        # Prefer headless download with retries when passphrase is stored.
        if kc_pass.load_passphrase():
            return self.begin_headless_download(
                app,
                destination_dir,
                try_purchase=try_purchase,
                external_version_id=external_version_id,
            )
        self._open_console_with_banner(args, banner=banner)
        return dest

    def download_result_path(self, destination_dir: str | Path) -> Path:
        return Path(destination_dir) / "download-result.json"

    def begin_headless_download(
        self,
        app: AppReference,
        destination_dir: str,
        *,
        try_purchase: bool = False,
        external_version_id: str | None = None,
        max_attempts: int = 5,
    ) -> Path:
        """Run tools/download-one.ps1 with stored passphrase and retries."""
        passphrase = kc_pass.load_passphrase()
        if not passphrase:
            raise RestoreError(
                ErrorCode.AUTHENTICATION_FAILED,
                "Нет сохранённого Keychain passphrase для фоновой загрузки.",
            )
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        script = self._resolve_tools_script("download-one.ps1")
        result_path = self.download_result_path(dest)
        if result_path.is_file():
            result_path.unlink()
        ps_args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-OutDir",
            str(dest),
            "-MaxAttempts",
            str(max_attempts),
        ]
        if app.bundle_id:
            ps_args.extend(["-BundleId", app.bundle_id])
        elif app.store_id:
            ps_args.extend(["-AppId", app.store_id])
        else:
            raise RestoreError(
                ErrorCode.APP_UNAVAILABLE,
                "Нужен bundle_id или store_id приложения.",
            )
        if external_version_id:
            ps_args.extend(["-ExternalVersionId", external_version_id])
        if try_purchase:
            ps_args.append("-TryPurchase")
        import os

        env = {**os.environ, "IPATOOL_KC_PASS": passphrase}
        logger.info(
            "Starting headless download script app=%s attempts=%s",
            app.store_id or app.bundle_id,
            max_attempts,
        )
        try:
            self._active_proc = subprocess.Popen(  # noqa: S603
                ps_args,
                cwd=str(script.parent),
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,  # type: ignore[attr-defined]
            )
        except OSError as exc:
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Не удалось запустить download-one.ps1.",
                details=str(exc),
            ) from exc
        return dest

    def cancel_active_process(self) -> bool:
        proc = self._active_proc
        if proc is None or proc.poll() is not None:
            self._active_proc = None
            return False
        try:
            proc.terminate()
        except OSError:
            return False
        self._active_proc = None
        return True

    def active_process_running(self) -> bool:
        proc = self._active_proc
        if proc is None:
            return False
        if proc.poll() is None:
            return True
        self._active_proc = None
        return False

    def read_download_result(self, destination_dir: str | Path) -> dict | None:
        path = self.download_result_path(destination_dir)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def begin_script_with_passphrase(
        self,
        script_name: str,
        extra_args: list[str] | None = None,
        *,
        cwd: Path | None = None,
    ) -> None:
        """Launch a tools/*.ps1 with IPATOOL_KC_PASS if stored, else interactive console."""
        script = self._resolve_tools_script(script_name)
        passphrase = kc_pass.load_passphrase()
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *(extra_args or []),
        ]
        env = None
        if passphrase:
            import os

            env = {**os.environ, "IPATOOL_KC_PASS": passphrase}
        if sys.platform != "win32":
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Скрипты ipatool сейчас поддерживаются на Windows.",
            )
        try:
            self._active_proc = subprocess.Popen(  # noqa: S603
                ["cmd.exe", "/k", subprocess.list2cmdline(args) + " & echo. & pause"],
                cwd=str(cwd or script.parent),
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
            )
        except OSError as exc:
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                f"Не удалось запустить {script_name}.",
                details=str(exc),
            ) from exc

    def versions_dump_path(self, destination_dir: str | Path, store_id: str) -> Path:
        return Path(destination_dir) / f"versions-{store_id}.json"

    def _resolve_tools_script(self, name: str) -> Path:
        script = self._tools_dir.parent / name
        if not script.is_file():
            script = self._tools_dir / name
        if not script.is_file():
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                f"Не найден tools/{name}",
                details=str(script),
            )
        return script

    def begin_interactive_list_versions(
        self,
        store_id: str,
        destination_dir: str | Path,
        *,
        enrich_limit: int = 40,
    ) -> Path:
        """Open PowerShell dump of list-versions (+ metadata for newest N)."""
        sid = (store_id or "").strip()
        if not sid.isdigit():
            raise RestoreError(
                ErrorCode.APP_UNAVAILABLE,
                "Для списка версий нужен числовой App Store ID.",
            )
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out_path = self.versions_dump_path(dest, sid)
        self.begin_script_with_passphrase(
            "list-versions-dump.ps1",
            ["-AppId", sid, "-EnrichLimit", str(int(enrich_limit))],
        )
        return out_path

    def load_versions_dump(self, path: str | Path) -> list[AppVersionInfo]:
        dump = Path(path)
        if not dump.is_file():
            raise RestoreError(
                ErrorCode.VERSIONS_FETCH_FAILED,
                f"Файл версий не найден: {dump.name}. "
                "Сначала завершите дамп в консоли (passphrase → DONE).",
                details=str(dump),
            )
        text = dump.read_text(encoding="utf-8-sig", errors="replace")
        versions = self._parse_versions(text)
        if not versions:
            raise RestoreError(
                ErrorCode.VERSIONS_FETCH_FAILED,
                "В дампе версий записей не найдено.",
                details=str(dump),
            )
        return versions

    @staticmethod
    def _parse_versions(stdout: str) -> list[AppVersionInfo]:
        text = (stdout or "").strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            blob = AppStoreCliAdapter._parse_json_blob(text)
            data = blob if blob is not None else {}

        versions: list[AppVersionInfo] = []
        if isinstance(data, dict):
            raw_list = data.get("versions")
            if isinstance(raw_list, list):
                for item in raw_list:
                    if not isinstance(item, dict):
                        continue
                    vid = item.get("externalVersionId") or item.get(
                        "externalVersionID"
                    )
                    if vid is None:
                        continue
                    versions.append(
                        AppVersionInfo(
                            external_version_id=str(vid).strip(),
                            display_version=(
                                str(item["displayVersion"]).strip()
                                if item.get("displayVersion")
                                else None
                            ),
                            release_date=(
                                str(item["releaseDate"]).strip()
                                if item.get("releaseDate")
                                else None
                            ),
                        )
                    )
            if not versions:
                ids = data.get("externalVersionIdentifiers")
                if isinstance(ids, list):
                    for vid in ids:
                        if vid is None:
                            continue
                        versions.append(
                            AppVersionInfo(external_version_id=str(vid).strip())
                        )
        return [v for v in versions if v.external_version_id]

    def begin_interactive_bulk_download(
        self,
        store_ids: list[str],
        destination_dir: str | Path,
        *,
        try_purchase: bool = False,
    ) -> Path:
        """Open PowerShell bulk download for numeric Store IDs (one passphrase)."""
        ids = [s.strip() for s in store_ids if str(s).strip().isdigit()]
        # Preserve order, unique.
        seen: set[str] = set()
        unique: list[str] = []
        for sid in ids:
            if sid not in seen:
                seen.add(sid)
                unique.append(sid)
        if not unique:
            raise RestoreError(
                ErrorCode.APP_UNAVAILABLE,
                "Нужен хотя бы один числовой App Store ID для массовой загрузки.",
            )
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        ids_file = dest / "bulk-ids.txt"
        ids_file.write_text("\n".join(unique) + "\n", encoding="utf-8")
        extra = ["-IdsFile", str(ids_file)]
        if try_purchase:
            extra.append("-TryPurchase")
        logger.info("Opening bulk download count=%s", len(unique))
        self.begin_script_with_passphrase("bulk-download.ps1", extra)
        return dest

    def purchases_dump_path(self, destination_dir: str | Path) -> Path:
        return Path(destination_dir) / "purchases-dump.json"

    def begin_interactive_list_purchases(self, destination_dir: str | Path) -> Path:
        """Open PowerShell dump script (stored passphrase or interactive prompt)."""
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out_path = self.purchases_dump_path(dest)
        self.begin_script_with_passphrase("list-purchases-dump.ps1")
        return out_path

    def load_purchases_dump(self, path: str | Path) -> list[PurchasedApp]:
        dump = Path(path)
        if not dump.is_file():
            raise RestoreError(
                ErrorCode.PURCHASES_FETCH_FAILED,
                f"Файл архива не найден: {dump.name}. "
                "Сначала завершите дамп в консоли (passphrase → DONE).",
                details=str(dump),
            )
        text = dump.read_text(encoding="utf-8-sig", errors="replace")
        apps = self._parse_purchases(text)
        if not apps:
            # jsonl fallback (one object per line)
            apps = []
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                apps.extend(self._parse_purchases(line))
        return apps

    def list_purchases(self) -> list[PurchasedApp]:
        """Headless list-purchases (often fails on Windows keyring — prefer interactive dump)."""
        ipatool = self._ipatool()
        result = self._runner.run(
            [str(ipatool), "list-purchases", "--format", "json", "-l", "50", "-p", "1"],
            timeout=180.0,
            cwd=str(self._tools_dir),
        )
        return self._parse_purchases(result.stdout)

    @staticmethod
    def _parse_purchases(stdout: str) -> list[PurchasedApp]:
        text = (stdout or "").strip()
        if not text:
            return []
        data: object
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try last JSON object in noisy console output.
            blob = AppStoreCliAdapter._parse_json_blob(text)
            data = blob if blob is not None else []

        items: list[object]
        if isinstance(data, dict):
            raw_apps = data.get("apps")
            if isinstance(raw_apps, list):
                items = raw_apps
            else:
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            items = []

        apps: list[PurchasedApp] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            store_raw = item.get("id") or item.get("appId") or item.get("storeId")
            store_id = str(store_raw).strip() if store_raw is not None else None
            if store_id == "":
                store_id = None
            bundle_id = item.get("bundleID") or item.get("bundleIdentifier")
            if isinstance(bundle_id, str):
                bundle_id = bundle_id.strip() or None
            else:
                bundle_id = None
            name = item.get("name") or item.get("title") or item.get("appName")
            if isinstance(name, str):
                name = name.strip() or None
            apps.append(
                PurchasedApp(
                    store_id=store_id,
                    bundle_id=bundle_id,
                    display_name=name,
                    version=item.get("version") if isinstance(item.get("version"), str) else None,
                    price=str(item["price"]) if item.get("price") is not None else None,
                    category=item.get("genre") if isinstance(item.get("genre"), str) else None,
                )
            )
        return apps

    @staticmethod
    def explain_download_failure(text: str) -> str:
        """User-facing hint for common ipatool download failures."""
        low = (text or "").lower()
        if "504" in low or "gateway timeout" in low:
            return (
                "Apple вернула HTTP 504 (таймаут витрины). "
                "Это сбой на стороне Store — повторите через минуту. "
                "При сохранённом passphrase iCarcas сам делает несколько попыток."
            )
        if "timeout" in low or "timed out" in low or "winhttp" in low:
            return (
                "Сеть/таймаут при обращении к Apple. "
                "Проверьте интернет/VPN и повторите — ретраи включены в фоновой загрузке."
            )
        if "license" in low or "licence" in low:
            return (
                "На этом Apple ID нет лицензии на приложение. "
                "Поиск ID только находит номер — скачать можно лишь то, "
                "что уже покупали/скачивали на этот аккаунт. "
                "Флаг «получить лицензию» работает только если приложение "
                "доступно в текущем регионе витрины."
            )
        if "password" in low or "passphrase" in low or "keychain" in low or "keyring" in low:
            return (
                "Проблема с Keychain passphrase / сессией. "
                "Сохраните passphrase заново или введите его в консоли."
            )
        if "login" in low or "auth" in low or "unauthor" in low or "session" in low:
            return "Сессия App Store неактивна. Сначала «Войти…»."
        if "not found" in low or "unavailable" in low or "no longer" in low:
            return (
                "Приложение недоступно для загрузки с текущей витрины, "
                "либо ID неверный. Если лицензия есть — попробуйте числовой Store ID."
            )
        return (
            "Загрузка не удалась. Проверьте консоль ipatool: "
            "лицензия, регион витрины и passphrase."
        )

    def search(self, term: str) -> list[AppSearchResult]:
        """Поиск приложений в App Store через ipatool search --format json."""
        ipatool = self._ipatool()
        result = self._runner.run(
            [str(ipatool), "search", term, "--format", "json"],
            timeout=120.0,
            cwd=str(self._tools_dir),
        )
        return self._parse_search_results(result.stdout)

    @staticmethod
    def _parse_search_results(stdout: str) -> list[AppSearchResult]:
        try:
            data = json.loads(stdout or "[]")
        except json.JSONDecodeError:
            data = []
        if not isinstance(data, list):
            data = [data]
        results: list[AppSearchResult] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            store_id = str(item.get("appId") or item.get("storeId") or "").strip() or None
            bundle_id = item.get("bundleIdentifier")
            if isinstance(bundle_id, str):
                bundle_id = bundle_id.strip() or None
            results.append(
                AppSearchResult(
                    store_id=store_id,
                    bundle_id=bundle_id,
                    display_name=item.get("title") or item.get("appName"),
                    version=item.get("version"),
                    price=item.get("price"),
                    category=item.get("genre"),
                )
            )
        return results

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
