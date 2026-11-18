from __future__ import annotations

from ios_restore.domain.errors import ErrorCode
from ios_restore.infrastructure.device_cli_adapter import DeviceCliAdapter


def test_map_passcode_error() -> None:
    err = DeviceCliAdapter._map_device_error(
        "Please enter the passcode on the device and retry.",
        fallback_message="x",
    )
    assert err.code == ErrorCode.DEVICE_TRUST_REQUIRED
    assert "Разблокируйте" in err.message


def test_map_hostid_error() -> None:
    err = DeviceCliAdapter._map_device_error(
        "Could not connect to lockdownd: Invalid HostID (-21)",
        fallback_message="x",
    )
    assert err.code == ErrorCode.DEVICE_TRUST_REQUIRED
