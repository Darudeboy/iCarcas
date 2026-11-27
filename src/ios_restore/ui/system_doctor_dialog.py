"""Non-blocking System Doctor dialog using existing services."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ios_restore.application.system_health_service import (
    HealthReport,
    HealthState,
    SystemHealthService,
)

_STATES = {
    HealthState.PASSED: "✓ Готово",
    HealthState.WARNING: "⚠ Внимание",
    HealthState.FAILED: "✕ Ошибка",
    HealthState.NOT_CHECKED: "— Не проверено",
    HealthState.UNSUPPORTED: "— Не поддерживается",
}


class _HealthSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _HealthWorker(QRunnable):
    def __init__(self, service: SystemHealthService) -> None:
        super().__init__()
        self.service = service
        self.signals = _HealthSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.service.check())
        except Exception:  # noqa: BLE001
            # Unexpected errors are not sent to UI verbatim.
            self.signals.failed.emit("Проверка прервана из-за внутренней ошибки.")


class SystemDoctorDialog(QDialog):
    def __init__(
        self,
        service: SystemHealthService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = QThreadPool.globalInstance()
        self.setWindowTitle("System Doctor — проверка iCarcas")
        self.resize(690, 540)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Безопасная диагностика: ничего не устанавливает, не меняет сессию "
            "Apple ID и не выполняет pairing. Наличие CLI не гарантирует, "
            "что он успешно запускается."
        )
        intro.setWordWrap(True)
        intro.setObjectName("hint")
        layout.addWidget(intro)
        self.summary = QLabel("Нажмите «Проверить систему».")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.list = QListWidget(self)
        self.list.setAlternatingRowColors(True)
        layout.addWidget(self.list, 1)
        self.refresh_button = QPushButton("Проверить систему")
        self.refresh_button.setProperty("variant", "primary")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        self.summary.setText("Выполняется проверка…")
        self.list.clear()
        worker = _HealthWorker(self._service)
        worker.signals.finished.connect(self._display_report)
        worker.signals.failed.connect(self._display_error)
        self._pool.start(worker)

    def _display_report(self, report: object) -> None:
        if not isinstance(report, HealthReport):
            self._display_error("Некорректный результат проверки.")
            return
        self.refresh_button.setEnabled(True)
        self.summary.setText(
            f"Проверено: {report.checked_at[:19].replace('T', ' ')} UTC · "
            f"Готово: {report.count(HealthState.PASSED)} · "
            f"Предупреждения: {report.count(HealthState.WARNING)} · "
            f"Ошибки: {report.count(HealthState.FAILED)} · "
            f"Не проверено: {report.count(HealthState.NOT_CHECKED)}"
        )
        for check in report.checks:
            label = _STATES[check.state]
            text = f"{label} · {check.title}\n{check.detail}"
            if check.advice:
                text += f"\nРекомендация: {check.advice}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, check.key)
            self.list.addItem(item)

    def _display_error(self, message: str) -> None:
        self.refresh_button.setEnabled(True)
        self.summary.setText(message)


def show_system_doctor(parent: QWidget, service: SystemHealthService) -> None:
    SystemDoctorDialog(service, parent).exec()
