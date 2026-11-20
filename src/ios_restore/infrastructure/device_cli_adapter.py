"""Real device adapter via libimobiledevice CLI tools."""

from __future__ import annotations

import logging
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import DeviceInfo
from ios_restore.infrastructure.paths import default_tools_dir, resolve_tool
from ios_restore.infrastructure.process_runner import ProcessRunner

logger = logging.getLogger("ios_restore.device")


class DeviceCliAdapter:
    def __init__(
        self,
        runner: ProcessRunner | None = None,
        tools_dir: Path | None = None,
    ) -> None:
        self._runner = runner or ProcessRunner()
        self._tools_dir = tools_dir or default_tools_dir()
        self._selected: DeviceInfo | None = None

    def list_devices(self) -> list[DeviceInfo]:
        idevice_id = resolve_tool("idevice_id", self._tools_dir)
        try:
            result = self._runner.run(
                [str(idevice_id), "-l"],
                timeout=30.0,
                check=False,
            )
        except RestoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RestoreError(
                ErrorCode.UNKNOWN_EXTERNAL_ERROR,
                "Не удалось запросить список устройств.",
                details=str(exc),
            ) from exc

        if result.returncode != 0:
            raise self._map_device_error(
                result.stderr or result.stdout,
                fallback_message="idevice_id завершился с ошибкой.",
            )

        udids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        devices: list[DeviceInfo] = []
        for udid in udids:
            devices.append(self._describe(udid))
        return devices

    def select_device(self, device_id: str) -> DeviceInfo:
        for device in self.list_devices():
            if device.device_id == device_id:
                if not device.available_for_operations:
                    raise RestoreError(
                        ErrorCode.DEVICE_TRUST_REQUIRED,
                        "Устройство обнаружено, но недоступно для операций "
                        "(проверьте доверие на экране устройства).",
                    )
                self._selected = device
                return device
        raise RestoreError(
            ErrorCode.DEVICE_NOT_FOUND,
            "Указанное устройство не найдено.",
            details=device_id,
        )

    def ensure_paired(self, device_id: str) -> None:
        idevicepair = resolve_tool("idevicepair", self._tools_dir)
        result = self._runner.run(
            [str(idevicepair), "-u", device_id, "validate"],
            timeout=30.0,
            check=False,
        )
        if result.returncode == 0:
            return
        # Attempt pair — user must confirm Trust on the phone.
        pair = self._runner.run(
            [str(idevicepair), "-u", device_id, "pair"],
            timeout=60.0,
            check=False,
        )
        if pair.returncode != 0:
            raise self._map_device_error(
                pair.stderr or pair.stdout,
                fallback_message=(
                    "Не удалось установить доверенную связь. "
                    "Разблокируйте устройство и нажмите «Доверять»."
                ),
            )

    def _describe(self, udid: str) -> DeviceInfo:
        name = self._info_key(udid, "DeviceName") or udid
        version = self._info_key(udid, "ProductVersion")
        available = True
        # If lockdown fails, treat as trust issue but still surface the UDID.
        if name == udid and version is None:
            # Try a lightweight probe: empty name from failed info.
            probe = self._raw_info(udid)
            if probe.returncode != 0:
                available = False
                err = (probe.stderr or probe.stdout or "").lower()
                if "trust" in err or "pair" in err or "password" in err:
                    name = f"{udid} (нужно доверие)"
        return DeviceInfo(
            device_id=udid,
            display_name=name,
            os_version=version,
            connection_type="usb",
            available_for_operations=available,
        )

    def _info_key(self, udid: str, key: str) -> str | None:
        ideviceinfo = resolve_tool("ideviceinfo", self._tools_dir)
        result = self._runner.run(
            [str(ideviceinfo), "-u", udid, "-k", key],
            timeout=20.0,
            check=False,
        )
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def _raw_info(self, udid: str):
        ideviceinfo = resolve_tool("ideviceinfo", self._tools_dir)
        return self._runner.run(
            [str(ideviceinfo), "-u", udid],
            timeout=20.0,
            check=False,
        )

    @staticmethod
    def _map_device_error(raw: str, *, fallback_message: str) -> RestoreError:
        text = raw or ""
        lower = text.lower()
        details = text[:500]
        if "passcode" in lower:
            return RestoreError(
                ErrorCode.DEVICE_TRUST_REQUIRED,
                "Устройство заблокировано. Разблокируйте экран код-паролем и повторите.",
                details=details,
            )
        if (
            "trust" in lower
            or "pair" in lower
            or "password" in lower
            or "hostid" in lower
            or "invalid hostid" in lower
            or "(-21)" in lower
        ):
            return RestoreError(
                ErrorCode.DEVICE_TRUST_REQUIRED,
                "Нужно доверие к компьютеру. Разблокируйте устройство и подтвердите «Доверять».",
                details=details,
            )
        return RestoreError(
            ErrorCode.UNKNOWN_EXTERNAL_ERROR,
            fallback_message,
            details=details,
        )
