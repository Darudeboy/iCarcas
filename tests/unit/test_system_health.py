"""System Doctor regression tests. No real device or Apple account required."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ios_restore.application.system_health_service import (
    HealthState,
    SystemHealthService,
)


@dataclass
class FakeComponent:
    key: str
    title: str
    ok: bool
    detail: str
    repairable: bool = True


class FakeDependencies:
    def check(self):
        return type("Report", (), {"components": (
            FakeComponent("ipatool", "ipatool", True, "/usr/bin/ipatool"),
            FakeComponent("device:idevice_id", "idevice_id", False, "не найден"),
        )})()


class FakeDevices:
    def __init__(self, devices=None, error=None):
        self.devices = devices or []
        self.error = error

    def list_devices(self):
        if self.error:
            raise self.error
        return self.devices


def test_system_doctor_reports_missing_dependency_and_session(tmp_path: Path) -> None:
    report = SystemHealthService(
        packages_dir=tmp_path,
        dependencies=FakeDependencies(),
        device_adapter=FakeDevices(),
        session_present=True,
    ).check()
    checks = {check.key: check for check in report.checks}
    assert checks["ipatool"].state == HealthState.PASSED
    assert checks["device:idevice_id"].state == HealthState.FAILED
    assert checks["apple_session"].state == HealthState.WARNING
    assert checks["device"].state == HealthState.WARNING
    assert report.count(HealthState.FAILED) >= 1


def test_system_doctor_does_not_claim_missing_directory_is_ready(tmp_path: Path) -> None:
    report = SystemHealthService(
        packages_dir=tmp_path / "not-created",
        dependencies=FakeDependencies(),
        device_adapter=FakeDevices(),
        session_present=False,
    ).check()
    checks = {check.key: check for check in report.checks}
    assert checks["packages_dir"].state == HealthState.FAILED
    assert checks["apple_session"].state == HealthState.NOT_CHECKED


def test_system_doctor_handles_device_probe_failure(tmp_path: Path) -> None:
    report = SystemHealthService(
        packages_dir=tmp_path,
        dependencies=FakeDependencies(),
        device_adapter=FakeDevices(error=RuntimeError("USB probe failed")),
    ).check()
    assert next(c for c in report.checks if c.key == "device").state == HealthState.WARNING
