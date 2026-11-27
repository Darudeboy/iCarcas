"""Диалог локальной истории скачиваний / установок."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ios_restore.domain.models import HistoryEntry


def show_history_dialog(
    parent,
    *,
    entries: list[HistoryEntry],
    dialog_qss: str,
) -> HistoryEntry | None:
    """Return selected entry on «Установить снова», else None."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"История ({len(entries)})")
    dialog.resize(820, 480)
    dialog.setStyleSheet(dialog_qss)
    layout = QVBoxLayout(dialog)
    layout.addWidget(
        QLabel(
            "Последние скачивания и установки. "
            "«Установить снова» подхватит IPA с диска, если файл ещё есть."
        )
    )

    filter_box = QComboBox(dialog)
    filter_box.addItems(["Все операции", "Скачивания", "Установки"])
    layout.addWidget(filter_box)

    table = QTableWidget(len(entries), 4, dialog)
    table.setHorizontalHeaderLabels(["Когда", "Действие", "Приложение", "Файл"])
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)

    for row, entry in enumerate(entries):
        when = entry.at.replace("T", " ")[:16]
        kind = "Скачано" if entry.kind == "download" else "Установлено"
        name = entry.display_name or entry.bundle_id or entry.store_id or "—"
        file_name = Path(entry.ipa_path).name if entry.ipa_path else "—"
        for col, text in enumerate((when, kind, name, file_name)):
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, row)
            table.setItem(row, col, item)

    def apply_filter(index: int) -> None:
        for row, entry in enumerate(entries):
            show = index == 0 or (
                index == 1 and entry.kind == "download"
            ) or (
                index == 2 and entry.kind == "install"
            )
            table.setRowHidden(row, not show)

    filter_box.currentIndexChanged.connect(apply_filter)
    table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(table)

    detail = QLabel("Выберите запись.")
    detail.setWordWrap(True)
    layout.addWidget(detail)

    def on_sel() -> None:
        row = table.currentRow()
        if row < 0 or row >= len(entries) or table.isRowHidden(row):
            return
        e = entries[row]
        detail.setText(
            f"{e.display_name or '—'}\n"
            f"{'Скачано' if e.kind == 'download' else 'Установлено'}: {e.at}\n"
            f"Store ID: {e.store_id or '—'} · bundle: {e.bundle_id or '—'}\n"
            f"IPA: {e.ipa_path or '—'}"
            + (f"\nУстройство: {e.device_name}" if e.device_name else "")
        )

    table.itemSelectionChanged.connect(on_sel)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
    use_btn = buttons.addButton(
        "Установить снова", QDialogButtonBox.ButtonRole.AcceptRole
    )
    layout.addWidget(buttons)

    chosen: dict[str, HistoryEntry | None] = {"entry": None}

    def on_use() -> None:
        row = table.currentRow()
        if row < 0 or row >= len(entries):
            QMessageBox.information(dialog, "История", "Выберите запись.")
            return
        entry = entries[row]
        if not entry.ipa_path or not Path(entry.ipa_path).is_file():
            QMessageBox.warning(
                dialog,
                "История",
                "Файл IPA уже не найден на диске.\n"
                "Скачайте приложение снова через поиск.",
            )
            return
        chosen["entry"] = entry
        dialog.accept()

    use_btn.clicked.connect(on_use)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return chosen["entry"]


def show_install_success_dialog(
    parent,
    *,
    app_name: str,
    device_name: str,
    version: str | None = None,
    dialog_qss: str = "",
) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Установка завершена")
    dialog.setMinimumWidth(420)
    if dialog_qss:
        dialog.setStyleSheet(dialog_qss)
    layout = QVBoxLayout(dialog)
    title = QLabel(app_name or "Приложение")
    title.setStyleSheet("font-size: 18px; font-weight: 700;")
    layout.addWidget(title)
    body = QLabel(
        f"Установлено на «{device_name}».\n"
        + (f"Версия: {version}\n" if version else "")
        + "Откройте приложение на iPhone / iPad — запуск из iCarcas не проверяется."
    )
    body.setWordWrap(True)
    layout.addWidget(body)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()
