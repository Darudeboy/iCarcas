"""First-run Terms of Use gate for personal iCarcas builds."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

TOS_VERSION = "1"
TOS_SETTINGS_KEY = "tos/accepted_version"

TOS_TEXT = (
    "iCarcas — личная утилита для восстановления приложений, "
    "доступных вашему Apple ID.\n\n"
    "Разрешено:\n"
    "• вход в свой Apple ID;\n"
    "• загрузка IPA, на которые у этого ID есть лицензия;\n"
    "• установка на свои устройства.\n\n"
    "Запрещено / не поддерживается:\n"
    "• обход DRM / FairPlay;\n"
    "• скачивание чужих покупок или пиратских IPA;\n"
    "• re-sign и jailbreak-сценарии.\n\n"
    "Поиск ID (каталог / iTunes) не даёт лицензию. "
    "Ошибки Apple (license is required, HTTP 504) — "
    "ограничения магазина, не баг обхода."
)


def tos_accepted(settings: QSettings | None = None) -> bool:
    store = settings or QSettings("iCarcas", "iCarcas")
    return str(store.value(TOS_SETTINGS_KEY, "")) == TOS_VERSION


def accept_tos(settings: QSettings | None = None) -> None:
    store = settings or QSettings("iCarcas", "iCarcas")
    store.setValue(TOS_SETTINGS_KEY, TOS_VERSION)


def ensure_tos_accepted(parent=None, settings: QSettings | None = None) -> bool:
    store = settings or QSettings("iCarcas", "iCarcas")
    if tos_accepted(store):
        return True
    dialog = QDialog(parent)
    dialog.setWindowTitle("Условия использования iCarcas")
    dialog.setMinimumWidth(480)
    layout = QVBoxLayout(dialog)
    label = QLabel(TOS_TEXT)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(label)
    check = QCheckBox("Понимаю и принимаю условия")
    layout.addWidget(check)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_btn is not None
    ok_btn.setEnabled(False)
    check.toggled.connect(ok_btn.setEnabled)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    accept_tos(store)
    return True
