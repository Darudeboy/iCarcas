"""Сервис поиска приложений в конкретном регионе App Store (iTunes Search API)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import KNOWN_REGIONS, AppSearchResult, AppStoreRegion
from ios_restore.domain.ports import RegionalSearchPort
from ios_restore.domain.search_query import relevance_score

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"


class RegionalAppSearchService:
    def __init__(self, adapter: RegionalSearchPort) -> None:
        self._adapter = adapter

    def search_region(self, term: str, region_code: str) -> list[AppSearchResult]:
        return self._adapter.search_region(term, region_code)

    @staticmethod
    def known_regions() -> tuple[AppStoreRegion, ...]:
        return KNOWN_REGIONS

    @staticmethod
    def region_by_code(code: str) -> AppStoreRegion | None:
        for region in KNOWN_REGIONS:
            if region.code == code:
                return region
        return None


class iTunesRegionalSearchAdapter:
    """Реализация RegionalSearchPort через публичный iTunes Search/Lookup API."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def search_region(self, term: str, region_code: str) -> list[AppSearchResult]:
        cleaned = (term or "").strip()
        if not cleaned:
            return []

        # Numeric Store ID → exact lookup (не «похожие» из search).
        if cleaned.isdigit():
            hit = self.lookup_id(cleaned, region_code)
            return [hit] if hit else []

        # Bundle id → lookup.
        if "." in cleaned and " " not in cleaned and not cleaned.startswith("http"):
            hit = self.lookup_bundle(cleaned, region_code)
            if hit:
                return [hit]

        raw_results = self._search_raw(cleaned, region_code)
        ranked = self._rank_and_filter(cleaned, region_code, raw_results)
        return ranked

    def lookup_id(self, store_id: str, region_code: str) -> AppSearchResult | None:
        data = self._get_json(
            ITUNES_LOOKUP_URL,
            {"id": store_id, "country": region_code},
        )
        return self._first_result(data, region_code, source="lookup")

    def lookup_bundle(self, bundle_id: str, region_code: str) -> AppSearchResult | None:
        data = self._get_json(
            ITUNES_LOOKUP_URL,
            {"bundleId": bundle_id, "country": region_code},
        )
        return self._first_result(data, region_code, source="lookup")

    def _search_raw(self, term: str, region_code: str) -> list[dict]:
        data = self._get_json(
            ITUNES_SEARCH_URL,
            {
                "term": term,
                "country": region_code,
                "entity": "software",
                "limit": "50",
            },
        )
        results = data.get("results", []) if isinstance(data, dict) else []
        return [item for item in results if isinstance(item, dict)]

    def _rank_and_filter(
        self,
        term: str,
        region_code: str,
        raw_results: list[dict],
    ) -> list[AppSearchResult]:
        scored: list[tuple[int, AppSearchResult]] = []
        for item in raw_results:
            app = self._item_to_result(item, region_code, source="itunes")
            score = relevance_score(
                query=term,
                display_name=app.display_name,
                bundle_id=app.bundle_id,
                store_id=app.store_id,
                seller_name=app.seller_name,
            )
            if score <= 0:
                continue
            scored.append((score, app))
        scored.sort(
            key=lambda pair: (
                -pair[0],
                (pair[1].display_name or "").casefold(),
            )
        )
        # Если после фильтра пусто — не подсовываем мусор (Instagram и т.п.).
        return [app for _, app in scored]

    def _get_json(self, base_url: str, params: dict[str, str]) -> dict:
        query = "&".join(
            f"{key}={urllib.parse.quote(str(value))}" for key, value in params.items()
        )
        url = f"{base_url}?{query}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            raise RestoreError(
                ErrorCode.REGIONAL_SEARCH_FAILED,
                "Не удалось выполнить запрос к iTunes API.",
                details=str(exc),
            ) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RestoreError(
                ErrorCode.REGIONAL_SEARCH_FAILED,
                "Неверный ответ от iTunes API.",
                details=str(exc),
            ) from exc
        if not isinstance(data, dict):
            return {}
        return data

    def _first_result(
        self,
        data: dict,
        region_code: str,
        *,
        source: str,
    ) -> AppSearchResult | None:
        results = data.get("results", [])
        if not isinstance(results, list) or not results:
            return None
        item = results[0]
        if not isinstance(item, dict):
            return None
        return self._item_to_result(item, region_code, source=source)

    def _item_to_result(
        self,
        item: dict,
        region_code: str,
        *,
        source: str,
    ) -> AppSearchResult:
        bundle_id = item.get("bundleId")
        store_id = item.get("trackId")
        return AppSearchResult(
            store_id=str(store_id) if store_id is not None else None,
            bundle_id=bundle_id if isinstance(bundle_id, str) else None,
            display_name=item.get("trackName") or item.get("artistName"),
            version=item.get("version") if isinstance(item.get("version"), str) else None,
            price=self._format_price(item.get("price"), item.get("currency")),
            category=(
                item.get("primaryGenreName")
                if isinstance(item.get("primaryGenreName"), str)
                else None
            ),
            region=region_code,
            source=source,
            seller_name=(
                item.get("sellerName") if isinstance(item.get("sellerName"), str) else None
            ),
        )

    @staticmethod
    def _format_price(price, currency) -> str | None:
        if price is None:
            return None
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return str(price)
        if price_val == 0:
            return "Бесплатно"
        return f"{price_val:.2f} {currency or ''}".strip()
