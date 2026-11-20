from __future__ import annotations

from ios_restore.application.license_check_service import LicenseCheckService
from ios_restore.domain.models import AppSearchResult, PurchasedApp


def test_licensed_when_in_purchases() -> None:
    svc = LicenseCheckService()
    result = svc.check(
        store_id="123",
        bundle_id=None,
        purchases=[PurchasedApp(store_id="123", display_name="Demo")],
        account_storefront="RU",
        app_region="RU",
    )
    assert result.status == "licensed"
    assert result.ok_to_download


def test_not_found_when_dump_loaded() -> None:
    svc = LicenseCheckService()
    result = svc.check(
        store_id="999",
        bundle_id=None,
        purchases=[PurchasedApp(store_id="123")],
    )
    assert result.status == "not_found"


def test_unknown_without_dump() -> None:
    svc = LicenseCheckService()
    result = svc.check(store_id="999", bundle_id=None, purchases=[])
    assert result.status == "unknown"


def test_region_mismatch() -> None:
    svc = LicenseCheckService()
    app = AppSearchResult(store_id="1", region="US")
    result = svc.check_search_result(
        app,
        purchases=[PurchasedApp(store_id="1")],
        account_storefront="RU",
    )
    assert result.status == "region_mismatch"
