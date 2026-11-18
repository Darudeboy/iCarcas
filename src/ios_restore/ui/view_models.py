"""UI-facing view models (no Qt dependency)."""

from __future__ import annotations

from dataclasses import dataclass

from ios_restore.application.restore_service import DemoScenarioResult
from ios_restore.domain.models import OperationStatus


@dataclass(frozen=True, slots=True)
class DemoViewState:
    status_text: str
    detail_text: str
    success: bool
    operation_id: str


def present_demo_result(result: DemoScenarioResult) -> DemoViewState:
    op = result.operation
    lines: list[str] = [
        f"Статус: {op.status.value}",
        f"Этап: {op.stage}",
        f"operation_id: {op.operation_id}",
    ]
    if result.tools:
        lines.append(f"Инструменты: {', '.join(result.tools)}")
    if result.device:
        lines.append(
            f"Устройство: {result.device.display_name} ({result.device.device_id})"
        )
    if result.auth_info:
        # Never show secrets; email from mock is demo-only.
        lines.append(f"Аккаунт (demo): {result.auth_info.get('email', '—')}")
    if result.package:
        lines.append(f"Пакет: {result.package.local_path}")
        lines.append(f"SHA-256: {result.package.sha256}")
        lines.append(
            f"bundle_id={result.package.bundle_id!s}, version={result.package.version!s}"
        )
    lines.append(op.user_message)
    if op.status == OperationStatus.SUCCEEDED:
        lines.append(
            "Важно: успех установки подтверждён только инструментом установки; "
            "запуск приложения не проверялся."
        )
    return DemoViewState(
        status_text=op.status.value,
        detail_text="\n".join(lines),
        success=op.status == OperationStatus.SUCCEEDED,
        operation_id=op.operation_id,
    )
