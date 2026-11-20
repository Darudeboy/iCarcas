#!/usr/bin/env python3
"""Cross-platform single IPA download with retries (macOS/Linux; Windows may use .ps1).

Env:
  IPATOOL_KC_PASS — Keychain passphrase
  IPATOOL_BIN — path to ipatool binary (optional)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text or "")


def _retryable(text: str) -> bool:
    low = _strip_ansi(text).lower()
    needles = (
        "http 504",
        "gateway timeout",
        "timeout",
        "timed out",
        "connection reset",
        "temporarily unavailable",
    )
    return any(n in low for n in needles)


def _success_text(text: str) -> bool:
    plain = _strip_ansi(text)
    if re.search(r"success[=:]?\s*false", plain, re.I) or re.search(
        r'"success"\s*:\s*false', plain, re.I
    ):
        return False
    if re.search(r"success[=:]?\s*true", plain, re.I) or re.search(
        r'"success"\s*:\s*true', plain, re.I
    ):
        return True
    return False


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _newest_ipa(out_dir: Path, after: float) -> Path | None:
    best: Path | None = None
    best_mtime = 0.0
    for path in out_dir.glob("*.ipa"):
        try:
            st = path.stat()
        except OSError:
            continue
        if st.st_size <= 1024:
            continue
        if st.st_mtime < after - 2:
            continue
        if st.st_mtime >= best_mtime:
            best = path
            best_mtime = st.st_mtime
    return best


def _partial_bytes(out_dir: Path, app_id: str) -> int:
    total = 0
    for path in out_dir.iterdir():
        name = path.name
        is_partial = (
            name.endswith(".ipa.tmp")
            or ".ipa.tmp." in name
            or "ipatool-parts" in name
        )
        if not is_partial:
            continue
        if app_id and not name.startswith(app_id):
            continue
        try:
            if path.is_file():
                total += path.stat().st_size
            elif path.is_dir():
                for part in path.rglob("*"):
                    if part.is_file():
                        total += part.stat().st_size
        except OSError:
            continue
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", default="")
    parser.add_argument("--bundle-id", default="")
    parser.add_argument("--external-version-id", default="")
    parser.add_argument("--try-purchase", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--passphrase", default="")
    args = parser.parse_args()

    tools_dir = Path(__file__).resolve().parent
    ipatool = Path(os.environ.get("IPATOOL_BIN") or "")
    if not ipatool.is_file():
        for name in ("ipatool", "ipatool.exe"):
            cand = tools_dir / "libimobiledevice" / name
            if cand.is_file():
                ipatool = cand
                break
        if not ipatool.is_file():
            ipatool = Path("ipatool")

    out_dir = Path(args.out_dir) if args.out_dir else tools_dir.parent / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_file = out_dir / "download-result.json"
    progress_file = out_dir / "download-progress.json"
    log_file = out_dir / "download-ipatool.log"

    passphrase = (args.passphrase or os.environ.get("IPATOOL_KC_PASS") or "").strip()
    if not passphrase:
        _write_json(
            result_file,
            {
                "success": False,
                "error": "Empty passphrase",
                "ipaPath": "",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        return 1

    if not args.app_id and not args.bundle_id:
        _write_json(
            result_file,
            {
                "success": False,
                "error": "Need --app-id or --bundle-id",
                "ipaPath": "",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        return 1

    started = time.time()
    log_file.write_text("", encoding="utf-8")

    for attempt in range(1, args.max_attempts + 1):
        _write_json(
            progress_file,
            {
                "phase": "download",
                "attempt": attempt,
                "maxAttempts": args.max_attempts,
                "bytes": _partial_bytes(out_dir, args.app_id),
                "expectedBytes": 0,
                "message": f"Attempt {attempt}/{args.max_attempts}",
                "appId": args.app_id,
                "bundleId": args.bundle_id,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        cmd = [
            str(ipatool),
            "--non-interactive",
            "--keychain-passphrase",
            passphrase,
            "--format",
            "json",
            "download",
            "-o",
            str(out_dir),
        ]
        if args.bundle_id:
            cmd.extend(["--bundle-identifier", args.bundle_id])
        else:
            cmd.extend(["--app-id", args.app_id])
        if args.external_version_id:
            cmd.extend(["--external-version-id", args.external_version_id])
        if args.try_purchase:
            cmd.append("--purchase")

        before = time.time()
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                cwd=str(tools_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            _write_json(
                result_file,
                {
                    "success": False,
                    "error": str(exc),
                    "ipaPath": "",
                    "finishedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
            return 1

        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n===== attempt {attempt} =====\n")
            fh.write(combined)

        ipa = _newest_ipa(out_dir, before)
        if proc.returncode == 0 or _success_text(combined) or ipa is not None:
            path = str(ipa) if ipa else ""
            _write_json(
                result_file,
                {
                    "success": True,
                    "error": "",
                    "ipaPath": path,
                    "reused": False,
                    "fresh": True,
                    "durationSec": round(time.time() - started, 1),
                    "finishedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
            _write_json(
                progress_file,
                {
                    "phase": "done",
                    "attempt": attempt,
                    "maxAttempts": args.max_attempts,
                    "bytes": ipa.stat().st_size if ipa else 0,
                    "expectedBytes": 0,
                    "message": "OK",
                    "appId": args.app_id,
                    "bundleId": args.bundle_id,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
            return 0

        if attempt < args.max_attempts and _retryable(combined):
            time.sleep(min(8, 2 * attempt))
            continue

        _write_json(
            result_file,
            {
                "success": False,
                "error": _strip_ansi(combined)[-2000:],
                "ipaPath": "",
                "durationSec": round(time.time() - started, 1),
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
