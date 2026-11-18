"""Background workers so the UI thread stays responsive."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ios_restore.application.restore_service import DemoScenarioResult, RestoreService
from ios_restore.domain.errors import RestoreError
from ios_restore.domain.models import AppReference, DeviceInfo, PackageInfo
from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter
from ios_restore.infrastructure.device_cli_adapter import DeviceCliAdapter
from ios_restore.infrastructure.install_cli_adapter import InstallCliAdapter


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class DemoScenarioWorker(QRunnable):
    def __init__(
        self,
        service: RestoreService,
        app: AppReference,
        *,
        confirm_install: bool = True,
        device_id: str | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.app = app
        self.confirm_install = confirm_install
        self.device_id = device_id
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result: DemoScenarioResult = self.service.run_demo_scenario(
                self.app,
                device_id=self.device_id,
                confirm_install=self.confirm_install,
            )
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class DetectDevicesWorker(QRunnable):
    def __init__(self, adapter: DeviceCliAdapter) -> None:
        super().__init__()
        self.adapter = adapter
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            devices = self.adapter.list_devices()
            self.signals.finished.emit(devices)
        except RestoreError as exc:
            self.signals.failed.emit(_format_restore_error(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class PairDeviceWorker(QRunnable):
    def __init__(self, adapter: DeviceCliAdapter, device_id: str) -> None:
        super().__init__()
        self.adapter = adapter
        self.device_id = device_id
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.adapter.ensure_paired(self.device_id)
            devices = self.adapter.list_devices()
            matched = next((d for d in devices if d.device_id == self.device_id), None)
            self.signals.finished.emit(
                matched or DeviceInfo(self.device_id, self.device_id)
            )
        except RestoreError as exc:
            self.signals.failed.emit(_format_restore_error(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class AuthInfoWorker(QRunnable):
    def __init__(self, adapter: AppStoreCliAdapter) -> None:
        super().__init__()
        self.adapter = adapter
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            info = self.adapter.auth_info()
            self.signals.finished.emit(info)
        except RestoreError as exc:
            self.signals.failed.emit(_format_restore_error(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class DownloadAppWorker(QRunnable):
    def __init__(
        self,
        adapter: AppStoreCliAdapter,
        app: AppReference,
        destination_dir: str,
    ) -> None:
        super().__init__()
        self.adapter = adapter
        self.app = app
        self.destination_dir = destination_dir
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            package = self.adapter.download(self.app, self.destination_dir)
            self.signals.finished.emit(package)
        except RestoreError as exc:
            self.signals.failed.emit(_format_restore_error(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class InstallAppWorker(QRunnable):
    def __init__(
        self,
        adapter: InstallCliAdapter,
        package: PackageInfo,
        device: DeviceInfo,
    ) -> None:
        super().__init__()
        self.adapter = adapter
        self.package = package
        self.device = device
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.adapter.install(self.package, self.device)
            self.signals.finished.emit(
                {
                    "device_id": self.device.device_id,
                    "package": self.package.local_path,
                }
            )
        except RestoreError as exc:
            self.signals.failed.emit(_format_restore_error(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


def _format_restore_error(exc: RestoreError) -> str:
    text = f"{exc.code.value}: {exc.message}"
    if exc.details:
        text += f"\n{exc.details}"
    return text
