from __future__ import annotations

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import DeviceInfo
from ios_restore.domain.ports import DevicePort


class DeviceService:
    def __init__(self, adapter: DevicePort) -> None:
        self._adapter = adapter

    def list_devices(self) -> list[DeviceInfo]:
        devices = self._adapter.list_devices()
        if not devices:
            raise RestoreError(
                ErrorCode.DEVICE_NOT_FOUND,
                "Подключённые устройства не обнаружены.",
            )
        return devices

    def require_single_or_selected(self, device_id: str | None = None) -> DeviceInfo:
        devices = self.list_devices()
        if device_id:
            return self._adapter.select_device(device_id)
        if len(devices) > 1:
            raise RestoreError(
                ErrorCode.DEVICE_SELECTION_REQUIRED,
                "Подключено несколько устройств; выберите одно.",
            )
        return self._adapter.select_device(devices[0].device_id)
