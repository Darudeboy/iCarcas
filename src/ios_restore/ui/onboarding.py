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
<h3>Как пользоваться</h3>
<ol>
<li><b>iPhone…</b> (угол) — подключите кабель → «Найти устройство» →
при необходимости «Установить доверие» (Trust на телефоне).</li>
<li><b>Войти…</b> (угол) — консоль: Apple ID, пароль и 2FA.
Если сессия уже была — «Проверить» / «Возобновить вход».</li>
<li><b>Запомнить ключ</b> — в меню сессии: Keychain passphrase (не пароль Apple ID).
Хранится только локально; с ним загрузки повторяются при сбоях сети.</li>
<li><b>Найти ID / каталог</b> — узнать номер приложения. Это ещё не лицензия.</li>
<li><b>Скачать IPA</b> — только если приложение уже было на этом Apple ID.</li>
<li><b>Установить</b> — на найденный iPhone.</li>
</ol>

<h3>Кнопки</h3>
<ul>
<li><b>iPhone… / Войти…</b> — компактное меню в правом верхнем углу.</li>
<li><b>Что нового</b> — изменения с последнего релиза (рядом со справкой).</li>
<li><b>Архив покупок</b> — список приложений с лицензией на аккаунте.</li>
<li><b>Подхватить архив / IPA</b> — прочитать результат после консоли.</li>
<li><b>Найти ID</b> — поиск в каталоге и App Store по региону.</li>
<li><b>Версии</b> — скачать не последнюю сборку (если Apple ещё отдаёт).</li>
<li><b>Каталог ID</b> — готовый список Store ID (в т.ч. снятые с витрины).</li>
<li><b>Диагностика</b> — zip без паролей и IPA для разбора проблем.</li>
</ul>

<h3>Приватность</h3>
<ul>
<li>Учётные данные и ключ сессии <b>хранятся только на этом компьютере</b>
и <b>никуда не передаются</b> (нет облака iCarcas).</li>
<li>Только <b>свой</b> Apple ID и <b>свои</b> покупки/загрузки.</li>
<li>Поиск ID ≠ право скачать. Без лицензии будет ошибка license.</li>
<li>Обход DRM / пиратские IPA не поддерживаются.</li>
<li>HTTP 504 — временный сбой Apple; при сохранённом ключе iCarcas повторит попытки.</li>
</ul>
"""

_PAGES: tuple[tuple[str, str], ...] = (
    (
        "Добро пожаловать в iCarcas",
        "Личная утилита: скачать свои приложения из App Store "
        "и поставить на свой iPhone.\n\n"
        "Дальше коротко — что делать и чего ждать.",
    ),
    (
        "Три шага",
        "1) В углу «iPhone…» — найти устройство.\n"
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


def show_help_dialog(parent: QWidget | None = None) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Справка — как пользоваться")
    dialog.resize(560, 520)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser(dialog)
    browser.setOpenExternalLinks(False)
    browser.setHtml(HELP_HTML)
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
    if close_btn:
        close_btn.clicked.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


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
