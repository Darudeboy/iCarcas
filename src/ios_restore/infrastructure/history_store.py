"""Локальная история скачиваний и установок (JSON рядом с packages)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ios_restore.domain.models import HistoryEntry, utc_now

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 80


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def list_entries(self, *, limit: int = 40) -> list[HistoryEntry]:
        raw = self._read()
        items = raw.get("entries")
        if not isinstance(items, list):
            return []
        out: list[HistoryEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            at = str(item.get("at") or "").strip()
            if kind not in {"download", "install"} or not at:
                continue
            out.append(
                HistoryEntry(
                    kind=kind,
                    at=at,
                    store_id=_opt_str(item.get("store_id")),
                    bundle_id=_opt_str(item.get("bundle_id")),
                    display_name=_opt_str(item.get("display_name")),
                    version=_opt_str(item.get("version")),
                    ipa_path=_opt_str(item.get("ipa_path")),
                    artwork_url=_opt_str(item.get("artwork_url")),
                    device_name=_opt_str(item.get("device_name")),
                )
            )
        return out[: max(1, limit)]

    def add(self, entry: HistoryEntry) -> None:
        raw = self._read()
        items = raw.get("entries")
        if not isinstance(items, list):
            items = []
        payload = {
            "kind": entry.kind,
            "at": entry.at,
            "store_id": entry.store_id,
            "bundle_id": entry.bundle_id,
            "display_name": entry.display_name,
            "version": entry.version,
            "ipa_path": entry.ipa_path,
            "artwork_url": entry.artwork_url,
            "device_name": entry.device_name,
        }
        items.insert(0, payload)
        raw["entries"] = items[:_MAX_ENTRIES]
        self._write(raw)

    def record_download(
        self,
        *,
        ipa_path: str,
        store_id: str | None = None,
        bundle_id: str | None = None,
        display_name: str | None = None,
        version: str | None = None,
        artwork_url: str | None = None,
    ) -> HistoryEntry:
        entry = HistoryEntry(
            kind="download",
            at=utc_now().isoformat(),
            store_id=store_id,
            bundle_id=bundle_id,
            display_name=display_name,
            version=version,
            ipa_path=ipa_path,
            artwork_url=artwork_url,
        )
        self.add(entry)
        return entry

    def record_install(
        self,
        *,
        ipa_path: str,
        device_name: str | None = None,
        store_id: str | None = None,
        bundle_id: str | None = None,
        display_name: str | None = None,
        version: str | None = None,
        artwork_url: str | None = None,
    ) -> HistoryEntry:
        entry = HistoryEntry(
            kind="install",
            at=utc_now().isoformat(),
            store_id=store_id,
            bundle_id=bundle_id,
            display_name=display_name,
            version=version,
            ipa_path=ipa_path,
            artwork_url=artwork_url,
            device_name=device_name,
        )
        self.add(entry)
        return entry

    def _read(self) -> dict:
        if not self._path.is_file():
            return {"entries": []}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("history read failed: %s", exc)
            return {"entries": []}
        return data if isinstance(data, dict) else {"entries": []}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
