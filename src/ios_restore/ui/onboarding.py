"""First-run onboarding + reusable help content for iCarcas."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ios_restore.ui.tos import TOS_TEXT, accept_tos, tos_accepted

ONBOARDING_VERSION = "1"
ONBOARDING_KEY = "onboarding/completed_version"

HELP_HTML = """
<p>
iCarcas — личная утилита для <b>iOS</b>: скачать приложения с вашего Apple ID
и поставить на <b>iPhone или iPad</b>. Учётные данные остаются только на этом ПК.
</p>
<p>
В углу: <b>iOS…</b> (кабель, «Доверять») и <b>Войти…</b> (Apple ID в консоли).
Дальше: найти ID → скачать IPA → <b>Установить на устройство</b>.
«Найти ID» лицензию не даёт — качается только то, что уже было на аккаунте.
</p>
<ul>
<li><b>Архив покупок</b> — приложения с лицензией на аккаунте.</li>
<li><b>Версии / Каталог ID</b> — старые сборки и список Store ID.</li>
<li><b>Диагностика</b> — zip без паролей и IPA.</li>
</ul>
"""

SETUP_HTML = """
<p>
На <b>новом компьютере</b> одного клона репозитория мало.
</p>
<p>
Нужны <b>Python 3.12+</b>, папка <code>tools/libimobiledevice</code>
(idevice_* и ipatool — их <b>нет в git clone</b>) и на Windows —
<b>Apple Mobile Device Support</b>
(<code>winget install --id Apple.AppleMobileDeviceSupport -e</code>).
Без этого устройство может быть видно в проводнике, но не в iCarcas.
</p>
<p>
Проверка: <code>.\\scripts\\check-tools.ps1</code>.
Подробности — README и <code>docs/setup.md</code>.
</p>
"""

_PAGES: tuple[tuple[str, str], ...] = (
    (
        "Добро пожаловать в iCarcas",
        "Личная утилита под iOS: скачать свои приложения из App Store "
        "и поставить на iPhone или iPad.\n\n"
        "Дальше коротко — что делать и чего ждать.",
    ),
    (
        "Три шага",
        "1) В углу «iOS…» — найти iPhone или iPad.\n"
        "2) В углу «Войти…» — свой Apple ID (пароль и 2FA в отдельной консоли).\n"
        "3) Найти приложение → скачать IPA → установить.\n\n"
        "Консоль спрашивает ещё Keychain passphrase — это не пароль Apple ID, "
        "а локальный ключ к сессии. Его можно запомнить на этом ПК; "
        "данные УЗ никуда не отправляются.",
    ),
    (
        "Лицензии и поиск",
        "Скачивается только то, что уже было на этом Apple ID "
        "(покупки / прошлые установки).\n\n"
        "«Найти ID» и каталог лишь подсказывают номер приложения. "
        "Без лицензии загрузка не пройдёт — это ограничение Apple, не баг.",
    ),
)


def onboarding_done(settings: QSettings | None = None) -> bool:
    store = settings or QSettings("iCarcas", "iCarcas")
    return str(store.value(ONBOARDING_KEY, "")) == ONBOARDING_VERSION


def mark_onboarding_done(settings: QSettings | None = None) -> None:
    store = settings or QSettings("iCarcas", "iCarcas")
    store.setValue(ONBOARDING_KEY, ONBOARDING_VERSION)


def _show_html_dialog(
    parent: QWidget | None,
    *,
    title: str,
    html: str,
    width: int = 520,
    height: int = 420,
) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(width, height)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser(dialog)
    browser.setOpenExternalLinks(False)
    browser.setHtml(html)
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
    if close_btn:
        close_btn.clicked.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


def show_help_dialog(parent: QWidget | None = None) -> None:
    _show_html_dialog(
        parent,
        title="Справка — как пользоваться",
        html=HELP_HTML,
        width=560,
        height=480,
    )


def show_setup_dialog(parent: QWidget | None = None) -> None:
    _show_html_dialog(
        parent,
        title="Справка — новый ПК",
        html=SETUP_HTML,
        width=520,
        height=360,
    )


class OnboardingDialog(QDialog):
    """Multi-page first-run guide ending with ToS acceptance."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Знакомство с iCarcas")
        self.setMinimumSize(520, 420)
        self._settings = QSettings("iCarcas", "iCarcas")

        root = QVBoxLayout(self)
        self.stack = QStackedWidget(self)
        for title, body in _PAGES:
            self.stack.addWidget(self._page(title, body))
        self.stack.addWidget(self._tos_page())
        root.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        self.back_btn = QPushButton("Назад")
        self.next_btn = QPushButton("Далее")
        self.next_btn.setDefault(True)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        self.page_label = QLabel()
        nav.addWidget(self.page_label)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

        self.back_btn.clicked.connect(self._back)
        self.next_btn.clicked.connect(self._next)
        self._tos_wired = False
        self._sync_nav()

    def _page(self, title: str, body: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        heading.setWordWrap(True)
        text = QLabel(body)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addStretch(1)
        return page

    def _tos_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Условия")
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        text = QLabel(TOS_TEXT)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tos_check = QCheckBox("Понимаю и принимаю условия")
        layout.addWidget(heading)
        layout.addWidget(text, 1)
        layout.addWidget(self.tos_check)
        return page

    def _sync_nav(self) -> None:
        idx = self.stack.currentIndex()
        total = self.stack.count()
        self.back_btn.setEnabled(idx > 0)
        self.page_label.setText(f"{idx + 1} / {total}")
        if idx == total - 1:
            self.next_btn.setText("Начать")
            self.next_btn.setEnabled(self.tos_check.isChecked())
            if not self._tos_wired:
                self.tos_check.toggled.connect(self.next_btn.setEnabled)
                self._tos_wired = True
        else:
            self.next_btn.setText("Далее")
            self.next_btn.setEnabled(True)

    def _back(self) -> None:
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._sync_nav()

    def _next(self) -> None:
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._sync_nav()
            return
        if not self.tos_check.isChecked():
            return
        accept_tos(self._settings)
        mark_onboarding_done(self._settings)
        self.accept()


def ensure_onboarding(parent: QWidget | None = None) -> bool:
    """
    Run onboarding once. Returns True if user can use the app
    (onboarding done + ToS accepted).
    """
    settings = QSettings("iCarcas", "iCarcas")
    if onboarding_done(settings) and tos_accepted(settings):
        return True
    dialog = OnboardingDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        # Allow continuing only if somehow already accepted ToS earlier.
        return tos_accepted(settings) and onboarding_done(settings)
    return True
