"""Deterministic mock adapters for stage-1 demo without Apple ID / device."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import AppReference, AppSearchResult, DeviceInfo, PackageInfo, PurchasedApp
from ios_restore.infrastructure.tool_registry import required_tool_names


class MockEnvironmentAdapter:
    def __init__(self, *, missing_tools: list[str] | None = None) -> None:
        self._missing = set(missing_tools or [])

    def check_tools(self) -> list[str]:
        ready = [name for name in required_tool_names() if name not in self._missing]
        if self._missing:
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                f"Не найдены инструменты: {', '.join(sorted(self._missing))}.",
            )
        return ready


class MockDeviceAdapter:
    def __init__(self, devices: list[DeviceInfo] | None = None) -> None:
        self._devices = devices or [
            DeviceInfo(
                device_id="00008030-001A2B3C4D5E6F79",
                display_name="Demo iPhone",
                os_version="17.5",
                connection_type="usb",
                available_for_operations=True,
            )
        ]
        self._selected: DeviceInfo | None = None

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices)

    def select_device(self, device_id: str) -> DeviceInfo:
        for device in self._devices:
            if device.device_id == device_id:
                if not device.available_for_operations:
                    raise RestoreError(
                        ErrorCode.DEVICE_TRUST_REQUIRED,
                        "Устройство обнаружено, но недоступно для операций "
                        "(возможно, требуется доверие).",
                    )
                self._selected = device
                return device
        raise RestoreError(
            ErrorCode.DEVICE_NOT_FOUND,
            "Указанное устройство не найдено.",
            details=device_id,
        )


class MockAuthAdapter:
    def __init__(self, *, fail: bool = False, require_2fa: bool = False) -> None:
        self._fail = fail
        self._require_2fa = require_2fa
        self._authenticated = False

    def begin_interactive_login(self) -> None:
        if self._require_2fa:
            raise RestoreError(
                ErrorCode.TWO_FACTOR_REQUIRED,
                "Требуется код двухфакторной аутентификации в поддерживаемом инструменте.",
            )
        if self._fail:
            raise RestoreError(
                ErrorCode.AUTHENTICATION_FAILED,
                "Авторизация не удалась.",
            )
        self._authenticated = True

    def auth_info(self) -> dict[str, str]:
        if not self._authenticated:
            raise RestoreError(
                ErrorCode.SESSION_EXPIRED,
                "Сессия не активна.",
            )
        return {
            "email": "demo@example.com",
            "name": "Demo User",
            "storefront": "RUS",
        }

    def revoke_session(self) -> None:
        self._authenticated = False


class MockDownloadAdapter:
    def __init__(
        self,
        *,
        fail_license: bool = False,
        fail_unavailable: bool = False,
        output_root: str | Path | None = None,
    ) -> None:
        self._fail_license = fail_license
        self._fail_unavailable = fail_unavailable
        self._output_root = Path(output_root or Path.cwd() / "packages")

    def download(self, app: AppReference, destination_dir: str) -> PackageInfo:
        if self._fail_license:
            raise RestoreError(
                ErrorCode.APP_LICENSE_MISSING,
                "У аккаунта нет права на это приложение.",
            )
        if self._fail_unavailable:
            raise RestoreError(
                ErrorCode.APP_UNAVAILABLE,
                "Приложение недоступно для загрузки.",
            )

        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        name = (app.bundle_id or app.store_id or "app").replace(".", "_")
        path = dest / f"{name}_demo.ipa"
        # Minimal zip-like bytes are not required for mock PackageInfo;
        # create a placeholder file for path/size/hash only.
        payload = b"PK\x03\x04DEMO_MOCK_IPA_NOT_A_REAL_PACKAGE\n"
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        return PackageInfo(
            local_path=str(path.resolve()),
            size_bytes=len(payload),
            sha256=digest,
            bundle_id=app.bundle_id or "com.example.demo",
            version="1.0.0",
            minimum_os_version="15.0",
        )


class MockInstallAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.installed: list[tuple[str, str]] = []

    def install(self, package: PackageInfo, device: DeviceInfo) -> None:
        if self._fail:
            raise RestoreError(
                ErrorCode.INSTALL_FAILED,
                "Инструмент установки сообщил об ошибке.",
            )
        self.installed.append((package.local_path, device.device_id))


class MockPurchasesAdapter:
    def __init__(
        self,
        apps: list[PurchasedApp] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self._apps = apps or [
            PurchasedApp(
                store_id="1051293689",
                bundle_id="com_example_demo_demo",
                display_name="Demo App",
                version="1.0.0",
                price="Бесплатно",
                category="Демо",
            ),
        ]
        self._fail = fail

    def list_purchases(self) -> list[PurchasedApp]:
        if self._fail:
            raise RestoreError(
                ErrorCode.PURCHASES_FETCH_FAILED,
                "Демо-ошибка получения архива покупок.",
            )
        return list(self._apps)


class MockSearchAdapter:
    def __init__(
        self,
        results: list[AppSearchResult] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self._results = results or [
            AppSearchResult(
                store_id="6737597349",
                bundle_id="com.deepseek.chat",
                display_name="DeepSeek AI Assistant",
                version="1.0.0",
                price="Бесплатно",
                category="Продуктивность",
            ),
            AppSearchResult(
                store_id="1051293689",
                bundle_id="com_example_demo_demo",
                display_name="Demo App",
                version="1.0.0",
                price="Бесплатно",
                category="Демо",
            ),
        ]
        self._fail = fail

    def search(self, term: str) -> list[AppSearchResult]:
        if self._fail:
            raise RestoreError(
                ErrorCode.SEARCH_FAILED,
                "Демо-ошибка поиска приложений.",
            )
        # Фильтруем по термину, если передан
        if term:
            lowered = term.lower()
            return [
                r for r in self._results
                if (r.display_name or "").lower().find(lowered) >= 0
                or (r.bundle_id or "").lower().find(lowered) >= 0
            ]
        return list(self._results)


class MockRegionalSearchAdapter:
    def __init__(
        self,
        results: list[AppSearchResult] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self._results = results or [
            AppSearchResult(
                store_id="6737597349",
                bundle_id="com.deepseek.chat",
                display_name="DeepSeek AI Assistant",
                version="1.0.0",
                price="Бесплатно",
                category="Продуктивность",
                region="US",
            ),
            AppSearchResult(
                store_id="1051293689",
                bundle_id="com_example_demo_demo",
                display_name="Demo App",
                version="1.0.0",
                price="Бесплатно",
                category="Демо",
                region="US",
            ),
        ]
        self._fail = fail

    def search_region(self, term: str, region_code: str) -> list[AppSearchResult]:
        if self._fail:
            raise RestoreError(
                ErrorCode.REGIONAL_SEARCH_FAILED,
                "Демо-ошибка регионального поиска.",
            )
        lowered = term.lower() if term else ""
        filtered = [
            r for r in self._results
            if (r.region or "").upper() == region_code.upper()
            and (
                not lowered
                or (r.display_name or "").lower().find(lowered) >= 0
                or (r.bundle_id or "").lower().find(lowered) >= 0
            )
        ]
        # Присваиваем регион результату
        return [
            AppSearchResult(
                store_id=r.store_id,
                bundle_id=r.bundle_id,
                display_name=r.display_name,
                version=r.version,
                price=r.price,
                category=r.category,
                region=region_code,
            )
            for r in filtered
        ]
