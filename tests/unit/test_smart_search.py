from ios_restore.application.smart_search_service import SmartAppSearchService
from ios_restore.domain.models import AppSearchResult, CatalogApp


class _FakeItunes:
    def search_region(self, term: str, region_code: str) -> list[AppSearchResult]:
        return [
            AppSearchResult(
                store_id="389801252",
                bundle_id="com.burbn.instagram",
                display_name="Instagram",
                region=region_code,
                source="itunes",
            ),
            AppSearchResult(
                store_id="6746730236",
                bundle_id="ru.alfabank.mobile.iphone",
                display_name="Kluch",
                region=region_code,
                source="itunes",
                seller_name="Alfa Bank",
            ),
        ]


def test_smart_search_prefers_catalog_and_drops_noise() -> None:
    catalog = [
        CatalogApp("Альфа-Банк (Оригинал)", "353127685"),
        CatalogApp("Альфа-Банк (Kluch)", "6746730236"),
        CatalogApp("Zvuk", "833449999"),
    ]
    # Patch: SmartAppSearchService uses RegionalAppSearchService(self._itunes)
    # so fake must be iTunes adapter-like. Easiest: subclass service path.
    svc = SmartAppSearchService(catalog=catalog)
    svc._regional.search_region = _FakeItunes().search_region  # type: ignore[method-assign]

    results = svc.search("Alfabank", "RU")
    ids = [r.store_id for r in results]
    assert "353127685" in ids
    assert "6746730236" in ids
    assert "389801252" not in ids
    assert results[0].store_id == "353127685"
    assert results[0].source and (
        results[0].source.startswith("catalog")
        or results[0].source.startswith("known")
    )


def test_smart_search_reports_api_outage_without_local_matches() -> None:
    import pytest

    from ios_restore.domain.errors import RestoreError

    svc = SmartAppSearchService(catalog=[])

    def unavailable(term: str, region: str) -> list[AppSearchResult]:
        raise RuntimeError("network unavailable")

    svc._regional.search_region = unavailable  # type: ignore[method-assign]
    with pytest.raises(RestoreError, match="App Store"):
        svc.search("UniqueUnknownApplication887723", "DE")
