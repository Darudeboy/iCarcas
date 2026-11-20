"""Resolve bundled / local tool directories."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    # src/ios_restore/infrastructure/paths.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def default_tools_dir() -> Path:
    return project_root() / "tools" / "libimobiledevice"


def resolve_tool(name: str, tools_dir: Path | None = None) -> Path:
    """Return absolute path to a tool executable if present locally or on PATH concept."""
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
    # Bare name fallback (PATH resolution at spawn time).
    return Path(stem if sys.platform != "win32" else f"{stem}.exe")
