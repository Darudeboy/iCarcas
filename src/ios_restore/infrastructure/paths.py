"""Resolve bundled / local tool directories."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    # src/ios_restore/infrastructure/paths.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def default_tools_dir() -> Path:
    return project_root() / "tools" / "libimobiledevice"


def resolve_tool(name: str, tools_dir: Path | None = None) -> Path:
    """Return absolute path to a tool executable if present locally or on PATH concept."""
    exe_name = name if name.lower().endswith(".exe") else f"{name}.exe"
    base = tools_dir or default_tools_dir()
    candidate = base / exe_name
    if candidate.is_file():
        return candidate
    # Bare name fallback (PATH resolution at spawn time).
    return Path(name)
