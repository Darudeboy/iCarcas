from ios_restore.application.smart_search_service import SmartAppSearchService
from ios_restore.domain.known_apps import resolve_known_apps
from ios_restore.domain.models import AppSearchResult, CatalogApp
from ios_restore.domain.search_query import relevance_score


def test_resolve_max() -> None:
    hits = resolve_known_apps("MAX")
    assert len(hits) == 1
    assert hits[0].store_id == "6739530834"


def test_resolve_match_tv() -> None:
    hits = resolve_known_apps("Матч ТВ")
    assert len(hits) == 1
    assert hits[0].store_id == "1051293689"
    assert hits[0].bundle_id == "com.ntvplus.matchclub"


def test_max_does_not_match_maxim_by_substring() -> None:
    assert (
        relevance_score(
            query="MAX",
            display_name="Такси Maxim",
            store_id="6752884875",
        )
        == 0
    )
    assert (
        relevance_score(
            query="MAX",
            display_name="MAX — мессенджер (Макс / ru.oneme.app)",
            store_id="6739530834",
            bundle_id="ru.oneme.app",
        )
        > 0
    )


def test_smart_search_max_pins_messenger() -> None:
    catalog = [
        CatalogApp("MAX — мессенджер (Макс / ru.oneme.app)", "6739530834"),
        CatalogApp("Такси Maxim", "6752884875"),
        CatalogApp("Zvuk", "833449999"),
    ]

    class _FakeRegional:
        def search_region(self, term: str, region_code: str) -> list[AppSearchResult]:
            return [
                AppSearchResult(
                    store_id="6477783496",
                    bundle_id="me.max.messenger",
                    display_name="MaxMessenger",
                    region=region_code,
                    source="itunes",
                    seller_name="Ali Naeem",
                ),
                AppSearchResult(
                    store_id="579985456",
                    bundle_id="com.taxsee.Taxsee",
                    display_name="maxim - заказ такси",
                    region=region_code,
                    source="itunes",
                ),
            ]

    svc = SmartAppSearchService(catalog=catalog)
    svc._regional.search_region = _FakeRegional().search_region  # type: ignore[method-assign]
    results = svc.search("MAX", "RU")
    assert results[0].store_id == "6739530834"
    assert "мессенджер" in (results[0].display_name or "").lower()
    ids = {r.store_id for r in results}
    assert "6752884875" not in ids
    assert "6477783496" not in ids
    assert "579985456" not in ids
