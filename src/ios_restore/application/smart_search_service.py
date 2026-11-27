"""Умный поиск Store ID: known apps + локальный каталог + iTunes."""

from __future__ import annotations

from ios_restore.application.regional_search_service import (
    RegionalAppSearchService,
    iTunesRegionalSearchAdapter,
)
from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.known_apps import KnownApp, resolve_known_apps
from ios_restore.domain.models import AppSearchResult, CatalogApp
from ios_restore.domain.search_query import (
    compact_text,
    relevance_score,
    search_query_variants,
    trim_by_relevance,
)
from ios_restore.infrastructure.apps_catalog import filter_catalog, load_apps_catalog


def _exclusive_known(known: list[KnownApp]) -> bool:
    return any(app.blocks_itunes for app in known)


class SmartAppSearchService:
    """
    Порядок:
    1) закреплённые known apps (MAX и т.п. — iTunes их часто не находит)
    2) локальный каталог (delisted)
    3) iTunes search с отсечением нерелевантного мусора
    """

    def __init__(
        self,
        itunes: iTunesRegionalSearchAdapter | None = None,
        *,
        catalog: list[CatalogApp] | None = None,
    ) -> None:
        self._itunes = itunes or iTunesRegionalSearchAdapter()
        self._regional = RegionalAppSearchService(self._itunes)
        self._catalog = catalog

    def _ensure_catalog(self) -> list[CatalogApp]:
        if self._catalog is None:
            try:
                self._catalog = load_apps_catalog()
            except Exception:  # noqa: BLE001
                self._catalog = []
        return self._catalog

    def search(self, term: str, region_code: str) -> list[AppSearchResult]:
        cleaned = (term or "").strip()
        if not cleaned:
            return []

        merged: dict[str, tuple[int, AppSearchResult]] = {}
        known = resolve_known_apps(cleaned)
        known_ids = {app.store_id for app in known}

        def add(app: AppSearchResult, score: int) -> None:
            key = app.store_id or f"{app.bundle_id}:{app.display_name}"
            if not key:
                return
            prev = merged.get(key)
            if prev is None or score > prev[0]:
                merged[key] = (score, app)

        # 0) Pinned known brands — always first when query matches.
        for rank, app in enumerate(known):
            add(
                AppSearchResult(
                    store_id=app.store_id,
                    bundle_id=app.bundle_id,
                    display_name=app.display_name,
                    version=None,
                    price=None,
                    category=None,
                    region=region_code,
                    source="known",
                    seller_name=None,
                ),
                10_000 - rank,
            )

        # 1) Catalog (delisted banks / messengers).
        catalog_hits = filter_catalog(self._ensure_catalog(), cleaned)
        for app in catalog_hits:
            display = app.display_name
            source = "catalog"
            boost = 500
            if app.store_id in known_ids:
                pinned = next(k for k in known if k.store_id == app.store_id)
                display = pinned.display_name
                source = "known+catalog"
                boost = 9_000
            result = AppSearchResult(
                store_id=app.store_id,
                bundle_id=next(
                    (k.bundle_id for k in known if k.store_id == app.store_id),
                    None,
                ),
                display_name=display,
                version=None,
                price=None,
                category=None,
                region=region_code,
                source=source,
                seller_name=None,
            )
            score = relevance_score(
                query=cleaned,
                display_name=app.display_name,
                store_id=app.store_id,
                source_boost=boost,
            )
            add(result, score)

        # 2) iTunes — several query variants, then relevance filter.
        exclusive = _exclusive_known(known)
        itunes_terms: list[str] = [] if exclusive else search_query_variants(cleaned)
        # Soft pins: also search by pinned titles (Дневник МЭШ и т.п.).
        if not exclusive:
            for app in known:
                if app.display_name and app.display_name not in itunes_terms:
                    itunes_terms.append(app.display_name)

        short_brand = len(compact_text(cleaned)) <= 4
        min_itunes_score = 140 if short_brand else 60

        search_failures = 0
        for iterm in itunes_terms:
            try:
                itunes_hits = self._regional.search_region(iterm, region_code)
            except Exception:  # noqa: BLE001
                search_failures += 1
                itunes_hits = []

            for app in itunes_hits:
                score = relevance_score(
                    query=cleaned,
                    display_name=app.display_name,
                    bundle_id=app.bundle_id,
                    store_id=app.store_id,
                    seller_name=app.seller_name,
                    source_boost=100 if app.source == "lookup" else 0,
                )
                existing = merged.get(app.store_id or "") if app.store_id else None
                if existing and (existing[1].source or "").startswith(
                    ("catalog", "known")
                ):
                    enriched = AppSearchResult(
                        store_id=app.store_id,
                        bundle_id=app.bundle_id or existing[1].bundle_id,
                        display_name=existing[1].display_name or app.display_name,
                        version=app.version,
                        price=app.price,
                        category=app.category,
                        region=region_code,
                        source=f"{existing[1].source}+itunes",
                        seller_name=app.seller_name,
                        artwork_url=app.artwork_url or existing[1].artwork_url,
                    )
                    add(enriched, max(existing[0], score) + 50)
                    continue
                if score < min_itunes_score:
                    continue
                add(app, score)

        if itunes_terms and search_failures == len(itunes_terms) and not merged:
            raise RestoreError(
                ErrorCode.REGIONAL_SEARCH_FAILED,
                "Не удалось связаться с App Store. Проверьте сеть и повторите поиск.",
            )

        ordered = sorted(
            merged.values(),
            key=lambda pair: (
                -pair[0],
                0
                if (pair[1].source or "").startswith(("known", "catalog"))
                else 1,
                (pair[1].display_name or "").casefold(),
            ),
        )
        trimmed = trim_by_relevance(list(ordered))
        return [app for _, app in trimmed]
