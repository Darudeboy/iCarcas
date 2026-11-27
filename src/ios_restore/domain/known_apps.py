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
    # If True and this pin matched — do not mix live iTunes noise (MAX и т.п.).
    blocks_itunes: bool = False


# Keep titles explicit so they are not confused with taxi / random "Max*" apps.
KNOWN_APPS: tuple[KnownApp, ...] = (
    # Main VK social network app. It may be absent from regional iTunes search
    # even when related VK services are returned. Keep the original Store ID
    # discoverable without claiming that the IPA is currently downloadable.
    KnownApp(
        store_id="564177498",
        display_name="ВКонтакте",
        bundle_id=None,
        queries=("vk", "вк", "вконтакте", "vkontakte"),
    ),
    KnownApp(
        store_id="6739530834",
        display_name="MAX — мессенджер (VK / ru.oneme.app)",
        bundle_id="ru.oneme.app",
        queries=("max", "макс", "maxmessenger", "мессенджерmax", "oneme"),
        blocks_itunes=True,
    ),
    KnownApp(
        store_id="833449999",
        display_name="Звук",
        bundle_id=None,
        queries=("звук", "zvuk"),
        blocks_itunes=True,
    ),
    KnownApp(
        store_id="353127685",
        display_name="Альфа-Банк (оригинал, delisted)",
        bundle_id=None,
        queries=("альфабанк", "alfabank", "alfabankоригинал"),
        blocks_itunes=True,
    ),
    KnownApp(
        store_id="1051293689",
        display_name="МАТЧ! — смотреть спорт онлайн (delisted)",
        bundle_id="com.ntvplus.matchclub",
        queries=(
            "матч",
            "матчтв",
            "матч!",
            "match",
            "matchtv",
            "matchclub",
            "ntvplusmatchclub",
        ),
        blocks_itunes=True,
    ),
    # Московская электронная школа — короткий «МЭШ» иначе ловит английский Mesh*.
    KnownApp(
        store_id="1475774929",
        display_name="Дневник МЭШ",
        bundle_id="ru.mes.dnevnik",
        queries=("мэш", "mes", "дневникмэш", "московскаяэлектроннаяшкола"),
    ),
    KnownApp(
        store_id="1619753967",
        display_name="Журнал МЭШ",
        bundle_id="ru.mos.school.journal",
        queries=("мэш", "mes", "журналмэш"),
    ),
    KnownApp(
        store_id="1260486799",
        display_name="Библиотека МЭШ",
        bundle_id="ru.mos.etbook",
        queries=("мэш", "mes", "библиотекамэш"),
    ),
    KnownApp(
        store_id="6508168563",
        display_name="Колледж МЭШ",
        bundle_id="ru.mes.diary.po",
        queries=("мэш", "mes", "колледжмэш"),
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
