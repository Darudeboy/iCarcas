"""Create a Desktop shortcut to iCarcas (Windows)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("ios_restore.desktop_shortcut")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_launch_target() -> Path | None:
    """Path that should be launched from the shortcut."""
    if is_frozen():
        return Path(sys.executable).resolve()
    # Dev: prefer a known launcher if present; otherwise None (skip auto-offer).
    return None


def desktop_dir() -> Path:
    home = Path.home()
    for candidate in (
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "Рабочий стол",
    ):
        if candidate.is_dir():
            return candidate
    return home / "Desktop"


def shortcut_path(name: str = "iCarcas.lnk") -> Path:
    return desktop_dir() / name


def shortcut_exists(name: str = "iCarcas.lnk") -> bool:
    return shortcut_path(name).is_file()


def create_desktop_shortcut(*, name: str = "iCarcas.lnk", force: bool = False) -> Path:
    """Create Desktop .lnk pointing at the portable exe. Windows only."""
    if sys.platform != "win32":
        raise OSError("Ярлык на рабочем столе поддерживается на Windows.")
    target = app_launch_target()
    if target is None or not target.is_file():
        raise OSError("Не найден iCarcas.exe — ярлык создаётся для portable-сборки.")
    link = shortcut_path(name)
    if link.is_file() and not force:
        return link
    workdir = str(target.parent)
    target_s = str(target)
    icon = target.parent / "assets" / "favicon.ico"
    icon_s = str(icon) if icon.is_file() else target_s
    # PowerShell COM — no pywin32 dependency.
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut({_ps_quote(str(link))}); "
        f"$s.TargetPath = {_ps_quote(target_s)}; "
        f"$s.WorkingDirectory = {_ps_quote(workdir)}; "
        f"$s.IconLocation = {_ps_quote(icon_s)}; "
        "$s.Description = 'iCarcas — свои приложения на iPhone'; "
        "$s.Save()"
    )
    import subprocess

    result = subprocess.run(  # noqa: S603
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    )
    if result.returncode != 0 or not link.is_file():
        detail = (result.stderr or result.stdout or "").strip()
        raise OSError(detail or "Не удалось создать ярлык на рабочем столе.")
    logger.info("Desktop shortcut created: %s -> %s", link, target)
    return link


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
