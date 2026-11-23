"""Check and repair local runtime dependencies (CLI, scripts, Apple drivers)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ios_restore.infrastructure.paths import default_tools_dir, project_root, resolve_tool

SUITE_URL = (
    "https://github.com/L1ghtmann/libimobiledevice/releases/download/"
    "suite-exe-21d57a9/libimobile-suite-latest_x86_64-mingw64.tar.xz"
)
IPATOOL_URL = (
    "https://github.com/majd/ipatool/releases/download/"
    "v2.8.1/ipatool-2.8.1-windows-amd64.tar.gz"
)
SCRIPTS_BASE = "https://raw.githubusercontent.com/Darudeboy/iCarcas/main/tools/"

DEVICE_TOOLS = (
    "idevice_id",
    "ideviceinfo",
    "idevicepair",
    "ideviceinstaller",
)

# Scripts live in tools/ (parent of libimobiledevice/).
REQUIRED_SCRIPTS_WIN = (
    "download-one.ps1",
    "list-versions-dump.ps1",
    "list-purchases-dump.ps1",
)
REQUIRED_SCRIPTS_UNIX = (
    "download_one.py",
    "list_versions_dump.py",
    "list_purchases_dump.py",
)


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    key: str
    title: str
    ok: bool
    detail: str
    repairable: bool = True


@dataclass(frozen=True, slots=True)
class DependencyReport:
    components: tuple[ComponentStatus, ...]

    @property
    def all_ok(self) -> bool:
        return all(c.ok for c in self.components)

    @property
    def missing(self) -> list[ComponentStatus]:
        return [c for c in self.components if not c.ok]


class DependencyService:
    def __init__(self, tools_dir: Path | None = None) -> None:
        self._tools_dir = tools_dir or default_tools_dir()
        self._root = project_root()
        self._scripts_dir = self._tools_dir.parent  # .../tools

    def check(self) -> DependencyReport:
        items: list[ComponentStatus] = []
        items.append(self._check_apple_mobile())
        items.append(self._check_ipatool())
        for name in DEVICE_TOOLS:
            items.append(self._check_device_tool(name))
        for name in self._required_scripts():
            items.append(self._check_script(name))
        catalog = self._root / "data" / "apps_catalog.txt"
        items.append(
            ComponentStatus(
                key="catalog",
                title="Каталог Store ID",
                ok=catalog.is_file(),
                detail=str(catalog) if catalog.is_file() else "data/apps_catalog.txt не найден",
                repairable=True,
            )
        )
        return DependencyReport(tuple(items))

    def repair(self, *, progress=None) -> DependencyReport:
        """Download/install missing pieces. progress(msg: str) optional callback."""

        def note(msg: str) -> None:
            if progress:
                progress(msg)

        report = self.check()
        missing_keys = {c.key for c in report.missing}

        if any(k.startswith("device:") or k == "ipatool" for k in missing_keys):
            note("Скачиваю libimobiledevice + ipatool…")
            self._ensure_cli_tools()

        script_names = [c.key.removeprefix("script:") for c in report.missing if c.key.startswith("script:")]
        if script_names:
            note("Ставлю скрипты tools/…")
            self._ensure_scripts(script_names)

        if "catalog" in missing_keys:
            note("Скачиваю каталог приложений…")
            self._ensure_catalog()

        if "apple_mobile" in missing_keys and sys.platform == "win32":
            note("Устанавливаю Apple Mobile Device Support (winget)…")
            self._install_apple_mobile()

        note("Проверяю ещё раз…")
        return self.check()

    def _required_scripts(self) -> tuple[str, ...]:
        if sys.platform == "win32":
            return REQUIRED_SCRIPTS_WIN
        return REQUIRED_SCRIPTS_UNIX

    def _check_apple_mobile(self) -> ComponentStatus:
        if sys.platform != "win32":
            return ComponentStatus(
                key="apple_mobile",
                title="Apple USB (драйверы)",
                ok=True,
                detail="На этой ОС не требуется Windows AMDS",
                repairable=False,
            )
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-Service -Name 'Apple Mobile Device Service' -ErrorAction SilentlyContinue).Status",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=flags,
            )
            status = (proc.stdout or "").strip()
            if status.lower() == "running":
                return ComponentStatus(
                    key="apple_mobile",
                    title="Apple Mobile Device Support",
                    ok=True,
                    detail="Служба Running",
                )
            if status:
                return ComponentStatus(
                    key="apple_mobile",
                    title="Apple Mobile Device Support",
                    ok=False,
                    detail=f"Служба: {status} (нужен Running)",
                )
        except Exception as exc:  # noqa: BLE001
            return ComponentStatus(
                key="apple_mobile",
                title="Apple Mobile Device Support",
                ok=False,
                detail=f"Не удалось проверить службу: {exc}",
            )
        return ComponentStatus(
            key="apple_mobile",
            title="Apple Mobile Device Support",
            ok=False,
            detail="Служба не найдена — установите драйверы Apple",
        )

    def _check_ipatool(self) -> ComponentStatus:
        path = resolve_tool("ipatool", self._tools_dir)
        ok = path.is_file()
        return ComponentStatus(
            key="ipatool",
            title="ipatool",
            ok=ok,
            detail=str(path) if ok else f"Нет файла в {self._tools_dir}",
        )

    def _check_device_tool(self, name: str) -> ComponentStatus:
        path = resolve_tool(name, self._tools_dir)
        ok = path.is_file()
        return ComponentStatus(
            key=f"device:{name}",
            title=name,
            ok=ok,
            detail=str(path) if ok else f"Нет файла в {self._tools_dir}",
        )

    def _check_script(self, name: str) -> ComponentStatus:
        path = self._scripts_dir / name
        ok = path.is_file()
        return ComponentStatus(
            key=f"script:{name}",
            title=name,
            ok=ok,
            detail=str(path) if ok else f"Нет tools/{name}",
        )

    def _ensure_cli_tools(self) -> None:
        self._tools_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="icarcas-tools-") as tmp:
            tmp_path = Path(tmp)
            suite_xz = tmp_path / "suite.tar.xz"
            self._download(SUITE_URL, suite_xz)
            # tarfile does not open .xz on all Windows builds — use system tar.
            subprocess.run(
                ["tar", "-xf", str(suite_xz), "-C", str(self._tools_dir)],
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            ipa_tg = tmp_path / "ipatool.tar.gz"
            self._download(IPATOOL_URL, ipa_tg)
            extract = tmp_path / "ipatool"
            extract.mkdir()
            with tarfile.open(ipa_tg, "r:gz") as tf:
                tf.extractall(extract)
            exe = next(extract.rglob("ipatool*.exe"), None) or next(
                extract.rglob("ipatool"), None
            )
            if exe is None:
                raise RuntimeError("ipatool не найден в архиве")
            target = self._tools_dir / ("ipatool.exe" if sys.platform == "win32" else "ipatool")
            shutil.copy2(exe, target)

    def _ensure_scripts(self, names: list[str]) -> None:
        self._scripts_dir.mkdir(parents=True, exist_ok=True)
        # Prefer copying from a source checkout next to portable root / known paths.
        local_candidates = [
            self._root / "tools",
            self._root.parent / "iCarcas" / "tools",
            Path(__file__).resolve().parents[3] / "tools",
        ]
        for name in names:
            dest = self._scripts_dir / name
            if dest.is_file():
                continue
            copied = False
            for base in local_candidates:
                src = base / name
                if src.is_file():
                    shutil.copy2(src, dest)
                    copied = True
                    break
            if copied:
                continue
            self._download(SCRIPTS_BASE + name, dest)

    def _ensure_catalog(self) -> None:
        dest = self._root / "data" / "apps_catalog.txt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            return
        local = Path(__file__).resolve().parents[3] / "data" / "apps_catalog.txt"
        if local.is_file():
            shutil.copy2(local, dest)
            return
        url = "https://raw.githubusercontent.com/Darudeboy/iCarcas/main/data/apps_catalog.txt"
        self._download(url, dest)

    def _install_apple_mobile(self) -> None:
        cmd = [
            "winget",
            "install",
            "--id",
            "Apple.AppleMobileDeviceSupport",
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--disable-interactivity",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # Always re-check via Get-Service afterwards; winget codes vary
        # (0, already-installed, reboot required, …).
        if proc.returncode != 0:
            out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).lower()
            if "already installed" in out or "no available upgrade" in out:
                return
            # Leave status for check(); tell user if still missing after repair.

    @staticmethod
    def _download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "iCarcas"})
        with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
            shutil.copyfileobj(resp, out)
