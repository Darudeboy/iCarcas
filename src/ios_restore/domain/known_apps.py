"""Pinned Store IDs for brands that iTunes search mangles or delists."""

from __future__ import annotations

from dataclasses import dataclass

from ios_restore.domain.search_query import compact_text


@dataclass(frozen=True, slots=True)
class KnownApp:
    store_id: str
    display_name: str
    bundle_id: str | None = None
    # Exact compact queries that should pin this app first.
    queries: tuple[str, ...] = ()


# Keep titles explicit so they are not confused with taxi / random "Max*" apps.
KNOWN_APPS: tuple[KnownApp, ...] = (
    KnownApp(
        store_id="6739530834",
        display_name="MAX — мессенджер (VK / ru.oneme.app)",
        bundle_id="ru.oneme.app",
        queries=("max", "макс", "maxmessenger", "мессенджерmax", "oneme"),
    ),
    KnownApp(
        store_id="833449999",
        display_name="Звук",
        bundle_id=None,
        queries=("звук", "zvuk"),
    ),
    KnownApp(
        store_id="353127685",
        display_name="Альфа-Банк (оригинал, delisted)",
        bundle_id=None,
        queries=("альфабанк", "alfabank", "alfabankоригинал"),
    ),
)


def resolve_known_apps(query: str) -> list[KnownApp]:
    """Return pinned apps for this query (may be empty)."""
    q = compact_text(query)
    if not q:
        return []
    hits: list[KnownApp] = []
    for app in KNOWN_APPS:
        aliases = {compact_text(a) for a in app.queries}
        if app.bundle_id:
            aliases.add(compact_text(app.bundle_id))
        if q in aliases:
            hits.append(app)
    return hits
