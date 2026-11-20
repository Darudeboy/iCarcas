"""Build a redacted diagnostics zip for personal support / debugging."""

from __future__ import annotations

import json
import platform
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ios_restore import __version__
from ios_restore.infrastructure.logging_setup import redact_secrets
from ios_restore.infrastructure.paths import default_tools_dir, project_root, resolve_tool
from ios_restore.infrastructure.tool_registry import KNOWN_TOOLS


def mask_udid(udid: str | None) -> str | None:
    if not udid:
        return None
    text = udid.strip()
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}…{text[-4:]}"


class DiagnosticsService:
    def __init__(
        self,
        *,
        packages_dir: Path,
        tools_dir: Path | None = None,
        session_present: bool = False,
        devices: list[dict] | None = None,
        log_text: str = "",
    ) -> None:
        self._packages_dir = packages_dir
        self._tools_dir = tools_dir or default_tools_dir()
        self._session_present = session_present
        self._devices = devices or []
        self._log_text = log_text

    def build_zip(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "app": "iCarcas",
            "version": __version__,
            "generated_at": datetime.now(UTC).isoformat(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "session_files_present": self._session_present,
            "project_root": str(project_root()),
            "packages_dir": str(self._packages_dir),
            "tools_dir": str(self._tools_dir),
            "tools": self._probe_tools(),
            "devices": [
                {
                    "device_id": mask_udid(d.get("device_id")),
                    "display_name": d.get("display_name"),
                    "os_version": d.get("os_version"),
                    "available": d.get("available_for_operations"),
                }
                for d in self._devices
            ],
            "packages_ipa_count": len(list(self._packages_dir.glob("*.ipa")))
            if self._packages_dir.is_dir()
            else 0,
        }
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
            zf.writestr("ui-log-redacted.txt", redact_secrets(self._log_text or "")[:200_000])
            # Explicitly do NOT add: .ipatool account/cookies, passphrase, IPA files.
            zf.writestr(
                "README.txt",
                "iCarcas diagnostics. No Apple passwords, keychain passphrase, "
                "cookies, or IPA files are included.\n",
            )
        return destination

    def _probe_tools(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for name, spec in KNOWN_TOOLS.items():
            path = resolve_tool(spec.executable, self._tools_dir)
            exists = path.is_file()
            out[name] = {"path": str(path), "exists": exists}
            if exists:
                out[name]["size"] = path.stat().st_size
        return out
