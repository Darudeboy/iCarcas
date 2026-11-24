"""Resolve bundled / local tool directories."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    # Portable .exe / .app: folder with the launcher (…/Contents/MacOS on macOS).
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/ios_restore/infrastructure/paths.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def default_packages_dir() -> Path:
    """Where IPA / dumps land. Frozen .app must not write into the bundle."""
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        return Path.home() / "Library" / "Application Support" / "iCarcas" / "packages"
    return Path.cwd() / "packages"


def default_tools_dir() -> Path:
    return project_root() / "tools" / "libimobiledevice"


def macos_brew_bin_dirs() -> tuple[Path, ...]:
    """Homebrew prefixes — Finder-launched .app often has a stripped PATH."""
    return (Path("/opt/homebrew/bin"), Path("/usr/local/bin"))


def find_brew() -> Path | None:
    which = shutil.which("brew")
    if which:
        return Path(which)
    for base in macos_brew_bin_dirs():
        cand = base / "brew"
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def resolve_tool(name: str, tools_dir: Path | None = None) -> Path:
    """Return absolute path to a tool if present locally, on PATH, or in Homebrew bins."""
    base = tools_dir or default_tools_dir()
    stem = name[:-4] if name.lower().endswith(".exe") else name
    candidates: list[str] = []
    if sys.platform == "win32":
        candidates.append(f"{stem}.exe")
        candidates.append(stem)
    else:
        candidates.append(stem)
        candidates.append(f"{stem}.exe")
    for exe_name in candidates:
        candidate = base / exe_name
        if candidate.is_file():
            return candidate

    which = shutil.which(stem) or (
        shutil.which(f"{stem}.exe") if sys.platform == "win32" else None
    )
    if which:
        return Path(which)

    if sys.platform == "darwin":
        for directory in macos_brew_bin_dirs():
            for exe_name in candidates:
                cand = directory / exe_name
                if cand.is_file() and os.access(cand, os.X_OK):
                    return cand

    # Bare name fallback (PATH resolution at spawn time).
    return Path(stem if sys.platform != "win32" else f"{stem}.exe")
