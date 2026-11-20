"""Ports (interfaces) for infrastructure adapters."""

from __future__ import annotations

from typing import Protocol

from ios_restore.domain.models import AppReference, AppSearchResult, DeviceInfo, PackageInfo, PurchasedApp


class EnvironmentPort(Protocol):
    def check_tools(self) -> list[str]:
        """Return names of tools that are ready; raise RestoreError if critical missing."""


class DevicePort(Protocol):
    def list_devices(self) -> list[DeviceInfo]:
        ...

    def select_device(self, device_id: str) -> DeviceInfo:
        ...


class AuthPort(Protocol):
    def begin_interactive_login(self) -> None:
        """Start tool-supported interactive auth (no password via argv)."""

    def auth_info(self) -> dict[str, str]:
        ...

    def revoke_session(self) -> None:
        ...


class DownloadPort(Protocol):
    def download(self, app: AppReference, destination_dir: str) -> PackageInfo:
        ...


class InstallPort(Protocol):
    def install(self, package: PackageInfo, device: DeviceInfo) -> None:
        ...


class PurchasesPort(Protocol):
    def list_purchases(self) -> list[PurchasedApp]:
        """Вернуть купленные/доступные приложения с бандлами (ipatool list-purchases)."""


class SearchPort(Protocol):
    def search(self, term: str) -> list[AppSearchResult]:
        """Поиск приложений в App Store по названию (ipatool search --format json)."""


class RegionalSearchPort(Protocol):
    def search_region(self, term: str, region_code: str) -> list[AppSearchResult]:
        """Поиск приложений в конкретном регионе App Store (iTunes Search API)."""


class PackageInspectorPort(Protocol):
    def inspect(self, path: str) -> PackageInfo:
        ...
