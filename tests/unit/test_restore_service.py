from __future__ import annotations

from pathlib import Path

from ios_restore.application.restore_service import RestoreService
from ios_restore.domain.models import AppReference, DeviceInfo, OperationStatus
from ios_restore.domain.operations import OperationStage
from ios_restore.infrastructure.mock_adapters import (
    MockAuthAdapter,
    MockDeviceAdapter,
    MockDownloadAdapter,
    MockEnvironmentAdapter,
    MockInstallAdapter,
)


def _service(tmp_path: Path, **overrides) -> RestoreService:
    kwargs = {
        "environment": MockEnvironmentAdapter(),
        "devices": MockDeviceAdapter(),
        "auth": MockAuthAdapter(),
        "download": MockDownloadAdapter(output_root=tmp_path),
        "install": MockInstallAdapter(),
        "packages_dir": tmp_path,
    }
    kwargs.update(overrides)
    return RestoreService(**kwargs)


def test_demo_happy_path(tmp_path: Path) -> None:
    install = MockInstallAdapter()
    service = _service(tmp_path, install=install)
    result = service.run_demo_scenario(
        AppReference(bundle_id="com.example.demo"),
        confirm_install=True,
    )
    assert result.operation.status == OperationStatus.SUCCEEDED
    assert result.operation.stage == OperationStage.INSTALLATION_REPORTED_SUCCESS.value
    assert "не проверялся" in result.operation.user_message
    assert len(install.installed) == 1
    assert result.package is not None
    assert result.package.bundle_id == "com.example.demo"


def test_no_false_success_on_license_error(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        download=MockDownloadAdapter(fail_license=True, output_root=tmp_path),
    )
    result = service.run_demo_scenario(AppReference(bundle_id="com.example.demo"))
    assert result.operation.status == OperationStatus.FAILED
    assert result.operation.error_code == "APP_LICENSE_MISSING"
    assert "работает" not in result.operation.user_message.lower()


def test_multiple_devices_require_selection(tmp_path: Path) -> None:
    devices = MockDeviceAdapter(
        [
            DeviceInfo("a", "Phone A"),
            DeviceInfo("b", "Phone B"),
        ]
    )
    service = _service(tmp_path, devices=devices)
    result = service.run_demo_scenario(AppReference(store_id="1"))
    assert result.operation.status == OperationStatus.FAILED
    assert result.operation.error_code == "DEVICE_SELECTION_REQUIRED"


def test_select_among_multiple(tmp_path: Path) -> None:
    devices = MockDeviceAdapter(
        [
            DeviceInfo("a", "Phone A"),
            DeviceInfo("b", "Phone B"),
        ]
    )
    service = _service(tmp_path, devices=devices)
    result = service.run_demo_scenario(
        AppReference(bundle_id="com.example.demo"),
        device_id="b",
    )
    assert result.operation.status == OperationStatus.SUCCEEDED
    assert result.device is not None
    assert result.device.device_id == "b"


def test_cancel_before_install(tmp_path: Path) -> None:
    install = MockInstallAdapter()
    service = _service(tmp_path, install=install)
    result = service.run_demo_scenario(
        AppReference(bundle_id="com.example.demo"),
        confirm_install=False,
    )
    assert result.operation.status == OperationStatus.CANCELLED
    assert install.installed == []
