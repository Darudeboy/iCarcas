"""Read-only, evidence-based system health checks.

These checks never install software, pair a device or authenticate an Apple ID.
A missing device is not confused with an unavailable device probe.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from ios_restore.application.dependency_service import DependencyService
from ios_restore.infrastructure.device_cli_adapter import DeviceCliAdapter
from ios_restore.infrastructure.logging_setup import redact_secrets


class HealthState(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    NOT_CHECKED = "not_checked"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class HealthCheck:
    key: str
    title: str
    state: HealthState
    detail: str
    advice: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    checks: tuple[HealthCheck, ...]
    checked_at: str

    def count(self, state: HealthState) -> int:
        return sum(check.state == state for check in self.checks)


class SystemHealthService:
    def __init__(
        self,
        *,
        packages_dir: Path,
        dependencies: DependencyService | None = None,
        device_adapter: DeviceCliAdapter | None = None,
        session_present: bool | None = None,
    ) -> None:
        self._packages_dir = packages_dir
        self._dependencies = dependencies or DependencyService()
        self._device_adapter = device_adapter or DeviceCliAdapter()
        self._session_present = session_present

    def check(self) -> HealthReport:
        checks: list[HealthCheck] = []
        try:
            dependencies = self._dependencies.check()
        except Exception as exc:  # noqa: BLE001
            checks.append(HealthCheck(
                "dependencies", "Системные компоненты", HealthState.FAILED,
                "Не удалось выполнить проверку компонентов.",
                redact_secrets(str(exc))[:300],
            ))
        else:
            for comp in dependencies.components:
                checks.append(HealthCheck(
                    comp.key, comp.title,
                    HealthState.PASSED if comp.ok else HealthState.FAILED,
                    "Компонент найден: " + comp.detail if comp.ok
                    else "Компонент не найден: " + comp.detail,
                    "" if comp.ok else (
                        "Откройте «Подготовка ПК» для исправления."
                        if comp.repairable else "Проверьте установку вручную."
                    ),
                ))

        checks.extend(self._check_storage())
        checks.append(self._check_device())
        checks.append(HealthCheck(
            "apple_session", "Сессия Apple ID",
            HealthState.WARNING if self._session_present else HealthState.NOT_CHECKED,
            "Файлы сессии обнаружены, но действительность входа не проверена."
            if self._session_present else "Действующая авторизация не подтверждена.",
            "Проверьте вход на вкладке Apple ID.",
        ))
        return HealthReport(tuple(checks), datetime.now(UTC).isoformat())

    def _check_storage(self) -> list[HealthCheck]:
        path = self._packages_dir
        try:
            if not path.is_dir():
                return [HealthCheck(
                    "packages_dir", "Каталог IPA", HealthState.FAILED,
                    "Папка загрузок не существует.",
                    "Создайте папку через настройки или проверьте путь.",
                )]
            # Do not write during diagnostics: existing folders are inspected read-only.
            # os.access is not a guarantee of effective permissions.
            import os

            if not os.access(path, os.W_OK):
                return [HealthCheck(
                    "packages_dir", "Каталог IPA", HealthState.FAILED,
                    "Нет разрешения на запись в каталог.",
                    "Выберите папку с разрешением на запись.",
                )]
            free = shutil.disk_usage(path).free
            minimum = 1024 * 1024 * 1024
            if free < minimum:
                return [HealthCheck(
                    "packages_dir", "Место для IPA", HealthState.WARNING,
                    f"Свободно {free / (1024 ** 3):.2f} ГБ (менее 1 ГБ).",
                    "Освободите место перед загрузкой.",
                )]
            return [HealthCheck(
                "packages_dir", "Место для IPA", HealthState.PASSED,
                f"Папка доступна; свободно {free / (1024 ** 3):.2f} ГБ. "
                "Запись не проверялась.",
            )]
        except OSError as exc:
            return [HealthCheck(
                "packages_dir", "Место для IPA", HealthState.FAILED,
                "Не удалось получить сведения о каталоге.",
                redact_secrets(str(exc))[:300],
            )]

    def _check_device(self) -> HealthCheck:
        try:
            devices = self._device_adapter.list_devices()
        except Exception as exc:  # noqa: BLE001
            return HealthCheck(
                "device", "Устройство", HealthState.WARNING,
                "Не удалось проверить подключённые устройства.",
                redact_secrets(str(exc))[:300],
            )
        if not devices:
            return HealthCheck(
                "device", "Устройство", HealthState.WARNING,
                "iPhone или iPad не обнаружен.",
                "Подключите устройство, разблокируйте его и повторите проверку.",
            )
        available = sum(device.available_for_operations for device in devices)
        return HealthCheck(
            "device", "Устройство",
            HealthState.PASSED if available else HealthState.WARNING,
            f"Обнаружено устройств: {len(devices)}; готовы к операциям: {available}.",
            "" if available else "Проверьте доверие к компьютеру на устройстве.",
        )
