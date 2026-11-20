"""Предварительная проверка лицензии до download IPA."""

from __future__ import annotations

from ios_restore.domain.models import AppSearchResult, LicenseCheckResult, PurchasedApp


class LicenseCheckService:
    """
    Оценка по локальному архиву покупок + региону витрины.

    Не гарантирует 100% (dump может быть неполным), но ловит явные «нет в покупках»
    и рассинхрон региона приложения с storefront аккаунта.
    """

    def check(
        self,
        *,
        store_id: str | None,
        bundle_id: str | None,
        app_region: str | None = None,
        purchases: list[PurchasedApp] | None = None,
        account_storefront: str | None = None,
    ) -> LicenseCheckResult:
        sid = (store_id or "").strip()
        bid = (bundle_id or "").strip()
        purchases = purchases or []

        hit = self._find_purchase(purchases, store_id=sid or None, bundle_id=bid or None)
        storefront = (account_storefront or "").strip().upper() or None
        region = (app_region or "").strip().upper() or None

        if hit is not None:
            if storefront and region and storefront != region:
                return LicenseCheckResult(
                    status="region_mismatch",
                    message=(
                        f"В архиве покупок есть, но регион приложения ({region}) "
                        f"не совпадает со storefront аккаунта ({storefront}). "
                        "Download может отказать."
                    ),
                    storefront=storefront,
                    app_region=region,
                )
            name = hit.display_name or sid or bid or "приложение"
            return LicenseCheckResult(
                status="licensed",
                message=f"Похоже, лицензия есть: «{name}» найдено в архиве покупок.",
                storefront=storefront,
                app_region=region,
            )

        if purchases:
            # Dump загружен, но ID нет — скорее всего нет лицензии.
            if storefront and region and storefront != region:
                return LicenseCheckResult(
                    status="region_mismatch",
                    message=(
                        f"В архиве покупок ID не найден. Плюс регион приложения ({region}) "
                        f"≠ storefront ({storefront})."
                    ),
                    storefront=storefront,
                    app_region=region,
                )
            return LicenseCheckResult(
                status="not_found",
                message=(
                    "В текущем архиве покупок этого Store ID / bundle нет. "
                    "Скачивание сработает только если лицензия всё же есть "
                    "(архив мог быть неполным) или включён --purchase."
                ),
                storefront=storefront,
                app_region=region,
            )

        if storefront and region and storefront != region:
            return LicenseCheckResult(
                status="region_mismatch",
                message=(
                    f"Архив покупок не загружен. Регион приложения ({region}) "
                    f"не совпадает со storefront ({storefront}) — высокий риск отказа."
                ),
                storefront=storefront,
                app_region=region,
            )

        return LicenseCheckResult(
            status="unknown",
            message=(
                "Лицензию заранее не проверить: нет архива покупок. "
                "Сделайте «Архив покупок…» → «Подхватить архив» для точной оценки."
            ),
            storefront=storefront,
            app_region=region,
        )

    def check_search_result(
        self,
        app: AppSearchResult,
        *,
        purchases: list[PurchasedApp] | None = None,
        account_storefront: str | None = None,
    ) -> LicenseCheckResult:
        return self.check(
            store_id=app.store_id,
            bundle_id=app.bundle_id,
            app_region=app.region,
            purchases=purchases,
            account_storefront=account_storefront,
        )

    @staticmethod
    def _find_purchase(
        purchases: list[PurchasedApp],
        *,
        store_id: str | None,
        bundle_id: str | None,
    ) -> PurchasedApp | None:
        for app in purchases:
            if store_id and app.store_id and app.store_id == store_id:
                return app
            if bundle_id and app.bundle_id and app.bundle_id == bundle_id:
                return app
        return None
