#!/usr/bin/env python3
"""Dump ipatool list-purchases into packages/purchases-dump.json (cross-platform)."""

from __future__ import annotations

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
    out_file = out_dir / "purchases-dump.json"

    page_size = 50
    page = 1
    total: int | None = None
    all_apps: list[object] = []
    print(f"Fetching purchases (page size {page_size})...")

    while True:
        cmd = [
            str(ipatool),
            "--non-interactive",
            "--keychain-passphrase",
            passphrase,
            "--format",
            "json",
            "list-purchases",
            "-l",
            str(page_size),
            "-p",
            str(page),
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
            print(f"Failed to parse page {page}")
            print(proc.stdout)
            print(proc.stderr)
            return 1
        if blob.get("success") is False:
            print(f"Error: {blob.get('error')}")
            return 1
        if total is None:
            try:
                total = int(blob.get("totalCount") or 0)
            except (TypeError, ValueError):
                total = 0
        apps = blob.get("apps") or []
        if not isinstance(apps, list):
            apps = []
        print(f"Page {page}: got {len(apps)} apps (total {total})")
        all_apps.extend(apps)
        if not apps:
            break
        if total is not None and len(all_apps) >= total:
            break
        page += 1
        if page > 200:
            break

    out_file.write_text(json.dumps(all_apps, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {len(all_apps)} apps to {out_file}")
    print("DONE. Return to iCarcas and click «Подхватить архив».")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
