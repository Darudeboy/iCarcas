"""Orchestrates the restore workflow using application services and domain FSM."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ios_restore.application.auth_service import AuthService
from ios_restore.application.device_service import DeviceService
from ios_restore.application.download_service import DownloadService
from ios_restore.application.environment_service import EnvironmentService
from ios_restore.application.install_service import InstallService
from ios_restore.domain.errors import RestoreError
from ios_restore.domain.models import (
    AppReference,
    DeviceInfo,
    OperationResult,
    PackageInfo,
    utc_now,
)
from ios_restore.domain.operations import OperationStage, RestoreWorkflow
from ios_restore.domain.ports import (
    AuthPort,
    DevicePort,
    DownloadPort,
    EnvironmentPort,
    InstallPort,
)


@dataclass(slots=True)
class DemoScenarioResult:
    operation: OperationResult
    device: DeviceInfo | None
    package: PackageInfo | None
    auth_info: dict[str, str] | None
    tools: list[str]


class RestoreService:
    def __init__(
        self,
        *,
        environment: EnvironmentPort,
        devices: DevicePort,
        auth: AuthPort,
        download: DownloadPort,
        install: InstallPort,
        packages_dir: str | Path | None = None,
    ) -> None:
        self.environment = EnvironmentService(environment)
        self.devices = DeviceService(devices)
        self.auth = AuthService(auth)
        self.download = DownloadService(download)
        self.install = InstallService(install)
        self.workflow = RestoreWorkflow()
        self.packages_dir = Path(packages_dir or Path.cwd() / "packages")
        self._device: DeviceInfo | None = None
        self._package: PackageInfo | None = None
        self._auth_info: dict[str, str] | None = None

    def run_demo_scenario(
        self,
        app: AppReference,
        *,
        device_id: str | None = None,
        confirm_install: bool = True,
    ) -> DemoScenarioResult:
        """Full happy-path demo without claiming the app launches on device."""
        result = OperationResult()
        result.started_at = utc_now()
        self.workflow.reset()
        self.workflow.ensure_can_start_parallel_guard()

        try:
            self._step_environment(result)
            self._step_device(result, device_id)
            self._step_auth(result)
            self._step_download(result, app)
            self._step_await_confirm(result)
            if not confirm_install:
                self.workflow.transition_to(OperationStage.CANCELLED)
                result.mark_cancelled(
                    OperationStage.CANCELLED.value,
                    "Установка не подтверждена пользователем.",
                )
                return self._build_result(result)

            self._step_install(result)
            result.mark_succeeded(
                OperationStage.INSTALLATION_REPORTED_SUCCESS.value,
                "Инструмент установки сообщил об успехе. "
                "Запуск приложения на устройстве не проверялся.",
            )
        except RestoreError as exc:
            if self.workflow.stage not in {
                OperationStage.FAILED,
                OperationStage.CANCELLED,
            }:
                try:
                    self.workflow.transition_to(OperationStage.FAILED)
                except RestoreError:
                    self.workflow.force_failed()
            result.mark_failed(
                exc.stage or self.workflow.stage.value,
                exc.code.value,
                self._user_error_message(exc, result.operation_id),
            )
        return self._build_result(result)

    def _step_environment(self, result: OperationResult) -> None:
        self.workflow.transition_to(OperationStage.CHECKING_ENVIRONMENT)
        result.mark_running(self.workflow.stage.value, "Проверка локального окружения…")
        tools = self.environment.verify()
        result.user_message = f"Инструменты готовы: {', '.join(tools)}"
        self._tools = tools

    def _step_device(self, result: OperationResult, device_id: str | None) -> None:
        self.workflow.transition_to(OperationStage.WAITING_FOR_DEVICE)
        result.mark_running(self.workflow.stage.value, "Поиск устройств…")
        self._device = self.devices.require_single_or_selected(device_id)
        result.user_message = f"Выбрано устройство: {self._device.display_name}"

    def _step_auth(self, result: OperationResult) -> None:
        self.workflow.transition_to(OperationStage.WAITING_FOR_USER_AUTH)
        result.mark_running(self.workflow.stage.value, "Ожидание авторизации…")
        self.workflow.transition_to(OperationStage.AUTHENTICATING)
        result.mark_running(self.workflow.stage.value, "Авторизация…")
        self._auth_info = self.auth.login_interactive()
        self.workflow.transition_to(OperationStage.READY)
        result.mark_running(self.workflow.stage.value, "Готово к загрузке.")

    def _step_download(self, result: OperationResult, app: AppReference) -> None:
        self.workflow.transition_to(OperationStage.DOWNLOADING)
        result.mark_running(self.workflow.stage.value, "Загрузка пакета…")
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self._package = self.download.download(app, str(self.packages_dir))
        self.workflow.transition_to(OperationStage.PACKAGE_READY)
        result.mark_running(
            self.workflow.stage.value,
            f"Пакет готов: {self._package.local_path}",
        )

    def _step_await_confirm(self, result: OperationResult) -> None:
        self.workflow.transition_to(OperationStage.WAITING_FOR_INSTALL_CONFIRMATION)
        result.mark_running(
            self.workflow.stage.value,
            "Ожидание подтверждения установки…",
        )

    def _step_install(self, result: OperationResult) -> None:
        assert self._package is not None
        assert self._device is not None
        self.workflow.transition_to(OperationStage.INSTALLING)
        result.mark_running(self.workflow.stage.value, "Установка на устройство…")
        self.install.install(self._package, self._device)
        self.workflow.transition_to(OperationStage.INSTALLATION_REPORTED_SUCCESS)

    def _build_result(self, result: OperationResult) -> DemoScenarioResult:
        return DemoScenarioResult(
            operation=result,
            device=self._device,
            package=self._package,
            auth_info=self._auth_info,
            tools=getattr(self, "_tools", []),
        )

    @staticmethod
    def _user_error_message(exc: RestoreError, operation_id: str) -> str:
        stage = exc.stage or "unknown"
        known = exc.message
        next_step = "Проверьте логи по идентификатору операции и повторите шаг."
        return (
            f"Этап: {stage}. Известно: {known} "
            f"Что делать: {next_step} "
            f"operation_id={operation_id}"
        )
