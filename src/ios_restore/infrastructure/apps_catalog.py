"""Local Apps ID catalog (ported from IPA_Downloader AppsList)."""

from __future__ import annotations

import re
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import CatalogApp
from ios_restore.domain.search_query import (
    query_needles,
    relevance_score,
    text_matches_needles,
)
from ios_restore.infrastructure.paths import project_root

_LINE_RE = re.compile(r"^\s*(.+?)\s*:\s*(\d{6,})\s*$")


def default_catalog_path() -> Path:
    return project_root() / "data" / "apps_catalog.txt"


def load_apps_catalog(path: Path | None = None) -> list[CatalogApp]:
    catalog = path or default_catalog_path()
    if not catalog.is_file():
        raise RestoreError(
            ErrorCode.CATALOG_LOAD_FAILED,
            f"Каталог ID не найден: {catalog.name}",
            details=str(catalog),
        )
    text = catalog.read_text(encoding="utf-8-sig", errors="replace")
    apps: list[CatalogApp] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        store_id = match.group(2)
        if store_id in seen:
            continue
        seen.add(store_id)
        apps.append(CatalogApp(display_name=name, store_id=store_id))
    if not apps:
        raise RestoreError(
            ErrorCode.CATALOG_LOAD_FAILED,
            "Каталог ID пуст или не разобран.",
            details=str(catalog),
        )
    return apps


def filter_catalog(apps: list[CatalogApp], query: str) -> list[CatalogApp]:
    q = (query or "").strip()
    if not q:
        return list(apps)
    needles = query_needles(q)
    scored: list[tuple[int, CatalogApp]] = []
    for app in apps:
        if q.isdigit() and app.store_id == q:
            scored.append((10_000, app))
            continue
        if q.isdigit() and q in app.store_id:
            # Partial Store ID (e.g. "8334" → Zvuk 833449999).
            scored.append((800 if app.store_id.startswith(q) else 500, app))
            continue
        if not text_matches_needles(app.display_name, needles):
            continue
        score = relevance_score(
            query=q,
            display_name=app.display_name,
            store_id=app.store_id,
            source_boost=300,
        )
        if score > 0:
            scored.append((score, app))
    scored.sort(key=lambda item: (-item[0], item[1].display_name.casefold()))
    return [app for _, app in scored]
