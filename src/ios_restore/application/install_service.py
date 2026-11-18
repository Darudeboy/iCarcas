from __future__ import annotations

from ios_restore.domain.models import DeviceInfo, PackageInfo
from ios_restore.domain.ports import InstallPort


class InstallService:
    def __init__(self, adapter: InstallPort) -> None:
        self._adapter = adapter

    def install(self, package: PackageInfo, device: DeviceInfo) -> None:
        self._adapter.install(package, device)
