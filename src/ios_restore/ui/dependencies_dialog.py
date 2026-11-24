"""Dialog: check PC components and install missing ones with one button."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ios_restore.application.dependency_service import DependencyReport, DependencyService
from ios_restore.ui.theme import repolish


class _RepairSignals(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)


class _RepairWorker(QRunnable):
    def __init__(self, service: DependencyService) -> None:
        super().__init__()
        self.service = service
        self.signals = _RepairSignals()

    @Slot()
    def run(self) -> None:  # noqa: N802
        try:
            report = self.service.repair(progress=self.signals.progress.emit)
            self.signals.finished.emit(report)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))


class DependenciesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Впервые здесь — проверка ПК")
        self.resize(620, 480)
        self._service = DependencyService()
        self._pool = QThreadPool.globalInstance()

        root = QVBoxLayout(self)
        intro = QLabel(
            "Чтобы программа увидела телефон и могла скачивать приложения, "
            "на компьютере нужны несколько служебных файлов и драйверы Apple.\n\n"
            "Нажмите «Установить недостающее» — всё подтянется само. "
            "Потом подключите телефон кабелем USB."
        )
        intro.setWordWrap(True)
        intro.setObjectName("hint")
        root.addWidget(intro)

        self.list = QListWidget(self)
        root.addWidget(self.list, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("hint")
        root.addWidget(self.status)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Проверить снова")
        self.refresh_btn.clicked.connect(self.refresh)
        self.repair_btn = QPushButton("Установить недостающее")
        self.repair_btn.setProperty("variant", "primary")
        repolish(self.repair_btn)
        self.repair_btn.clicked.connect(self._on_repair)
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        row.addWidget(self.repair_btn)
        root.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        root.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        report = self._service.check()
        self._fill(report)

    def _fill(self, report: DependencyReport) -> None:
        self.list.clear()
        for comp in report.components:
            mark = "OK" if comp.ok else "НЕТ"
            item = QListWidgetItem(f"[{mark}]  {comp.title}\n      {comp.detail}")
            item.setData(Qt.ItemDataRole.UserRole, comp.key)
            self.list.addItem(item)
        missing = report.missing
        if not missing:
            self.status.setText("Всё на месте. Можно закрыть окно и пользоваться программой.")
            self.repair_btn.setEnabled(False)
        else:
            names = ", ".join(c.title for c in missing)
            self.status.setText(f"Не хватает: {names}")
            self.repair_btn.setEnabled(any(c.repairable for c in missing))

    def _on_repair(self) -> None:
        self.repair_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.status.setText("Установка… это может занять несколько минут.")
        worker = _RepairWorker(self._service)
        worker.signals.progress.connect(self.status.setText)
        worker.signals.finished.connect(self._on_repaired)
        worker.signals.failed.connect(self._on_repair_failed)
        self._pool.start(worker)

    def _on_repaired(self, report: object) -> None:
        self.refresh_btn.setEnabled(True)
        assert isinstance(report, DependencyReport)
        self._fill(report)
        if report.all_ok:
            QMessageBox.information(
                self,
                "Готово",
                "Компоненты установлены. Подключите устройство кабелем, "
                "нажмите «Доверять» и в углу — «iOS… → Найти устройство».",
            )
        else:
            still = ", ".join(c.title for c in report.missing)
            QMessageBox.warning(
                self,
                "Ещё не всё",
                "Часть компонентов всё ещё отсутствует:\n"
                f"{still}\n\n"
                "Для Apple Mobile Device Support может понадобиться запуск от администратора:\n"
                "winget install --id Apple.AppleMobileDeviceSupport -e",
            )

    def _on_repair_failed(self, message: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.repair_btn.setEnabled(True)
        self.status.setText("Ошибка установки.")
        QMessageBox.warning(self, "Установка", message)
        self.refresh()


def show_dependencies_dialog(parent: QWidget | None = None) -> None:
    dialog = DependenciesDialog(parent)
    dialog.exec()
