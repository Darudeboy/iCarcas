#!/usr/bin/env python3
"""Dump ipatool list-versions into packages/versions-{id}.json (cross-platform)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _ipatool_bin(tools_dir: Path) -> Path:
    env = os.environ.get("IPATOOL_BIN")
    if env and Path(env).is_file():
        return Path(env)
    for name in ("ipatool", "ipatool.exe"):
        cand = tools_dir / "libimobiledevice" / name
        if cand.is_file():
            return cand
    return Path("ipatool")


def _parse_json_blob(text: str) -> dict | None:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text or "")
    for line in reversed(plain.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--enrich-limit", type=int, default=40)
    args = parser.parse_args()
    if not args.app_id.isdigit():
        print(f"AppId must be numeric, got: {args.app_id}")
        return 1

    tools_dir = Path(__file__).resolve().parent
    ipatool = _ipatool_bin(tools_dir)
    passphrase = (os.environ.get("IPATOOL_KC_PASS") or "").strip()
    if not passphrase:
        try:
            passphrase = input("Keychain passphrase (NOT Apple ID password): ").strip()
        except EOFError:
            passphrase = ""
    if not passphrase:
        print("Empty passphrase, abort.")
        return 1

    out_dir = tools_dir.parent / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"versions-{args.app_id}.json"

    print(f"Fetching version IDs for app {args.app_id}...")
    cmd = [
        str(ipatool),
        "--non-interactive",
        "--keychain-passphrase",
        passphrase,
        "--format",
        "json",
        "list-versions",
        "-i",
        args.app_id,
    ]
    proc = subprocess.run(  # noqa: S603
        cmd,
        cwd=str(tools_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    blob = _parse_json_blob((proc.stdout or "") + "\n" + (proc.stderr or ""))
    if not isinstance(blob, dict):
        print("Failed to parse list-versions output")
        print(proc.stdout)
        print(proc.stderr)
        return 1
    if blob.get("success") is False:
        print(f"Error: {blob.get('error')}")
        return 1

    # Normalize to { versions: [...] } when ipatool returns externalVersionIds list.
    if "versions" not in blob:
        ids = blob.get("externalVersionIds") or blob.get("externalVersionIDs") or []
        if isinstance(ids, list):
            blob = {
                "success": True,
                "versions": [{"externalVersionId": str(v)} for v in ids],
            }
    out_file.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {out_file}")
    print("DONE. Return to iCarcas and click «Подхватить версии».")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
