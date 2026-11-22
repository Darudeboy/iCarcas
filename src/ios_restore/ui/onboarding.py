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
<p><b>iCarcas</b> скачивает <b>ваши</b> приложения из App Store и ставит на iPhone/iPad.
Пароли остаются только на этом компьютере.</p>
<ol>
<li><b>iOS…</b> — подключить кабель, «Доверять», найти устройство.</li>
<li><b>Войти…</b> — Apple ID в консоли (пароль и код).</li>
<li>Найти ID → скачать IPA → <b>Установить на устройство</b>.</li>
</ol>
<p>Скачивается только то, что уже было на этом Apple ID.
«Найти ID» само по себе право скачать не даёт.</p>
"""

SETUP_HTML = """
<p><b>Первая установка</b> — сделайте три шага, иначе iPhone/iPad в программе не появится:</p>
<ol>
<li><b>Python 3.12+</b> и <code>pip install -e ".[dev]"</code></li>
<li>Положите утилиты в <code>tools\\libimobiledevice</code>
(их нет в git) — см. README</li>
<li>Windows: <code>winget install --id Apple.AppleMobileDeviceSupport -e</code></li>
</ol>
<p>Проверка: <code>.\\scripts\\check-tools.ps1</code>.
Дальше: кабель → «Доверять» → в углу <b>iOS… → Найти устройство</b>.</p>
"""

_PAGES: tuple[tuple[str, str], ...] = (
    (
        "Добро пожаловать в iCarcas",
        "Скачиваем ваши приложения из App Store и ставим на iPhone или iPad.\n"
        "Данные остаются только на этом компьютере.",
    ),
    (
        "Три шага",
        "1) «iOS…» — найти устройство.\n"
        "2) «Войти…» — свой Apple ID в консоли.\n"
        "3) Найти ID → скачать → установить.\n\n"
        "Консоль может спросить passphrase — это не пароль Apple ID, "
        "а локальный ключ. Его можно сохранить на этом ПК.",
    ),
    (
        "Важно",
        "Качается только то, что уже было на вашем Apple ID.\n"
        "Если лицензии нет — будет ошибка Apple, это не баг iCarcas.",
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
        title="Впервые здесь — первая установка",
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
