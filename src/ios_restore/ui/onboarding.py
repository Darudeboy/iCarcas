"""First-run onboarding + reusable help content for iCarcas."""

from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ios_restore.infrastructure import desktop_shortcut as desk
from ios_restore.ui.tos import TOS_TEXT, accept_tos, tos_accepted

# Bump when first-run copy changes so existing installs see the simpler guide once.
ONBOARDING_VERSION = "2"
ONBOARDING_KEY = "onboarding/completed_version"

HELP_HTML = """
<p><b>iCarcas</b> ставит на ваш iPhone или iPad приложения, которые уже были
на <b>вашем</b> Apple ID. Пароли никуда не отправляются.</p>

<h3>Как пользоваться</h3>
<ol>
<li>Возьмите <b>кабель USB</b>, подключите телефон к компьютеру и
<b>разблокируйте</b> экран. На телефоне нажмите <b>«Доверять»</b>.</li>
<li>Справа вверху нажмите <b>«Телефон…»</b> → «Найти телефон».</li>
<li>Нажмите <b>«Apple ID…»</b> → «Войти». Откроется чёрное окно —
введите логин, пароль и код из SMS. Это нормально.</li>
<li>Найдите приложение → <b>«Скачать»</b> → <b>«Установить на устройство»</b>.</li>
</ol>

<p>Если телефон не находится — кнопка <b>«Впервые здесь?»</b>: проверка
и установка нужных компонентов одной кнопкой.</p>

<p>Скачивается только то, что уже покупали или ставили на этом Apple ID.
Просто найти название в поиске — ещё не значит, что можно скачать.</p>
"""

_PAGES: tuple[tuple[str, str], ...] = (
    (
        "Добро пожаловать",
        "iCarcas помогает вернуть на iPhone или iPad ваши приложения из App Store.\n\n"
        "Нужны только кабель USB и ваш Apple ID.\n"
        "Пароль остаётся на этом компьютере — в интернет «на сторону» он не уходит.",
    ),
    (
        "Подключите телефон",
        "1. Возьмите обычный кабель USB (тот, которым заряжаете телефон).\n"
        "2. Вставьте в компьютер и в iPhone / iPad.\n"
        "3. Разблокируйте телефон.\n"
        "4. На экране телефона нажмите «Доверять этому компьютеру».\n\n"
        "Потом в программе справа вверху: кнопка «Телефон…» → «Найти телефон».\n"
        "Когда телефон найден, кнопка станет зелёной.",
    ),
    (
        "Войдите в Apple ID",
        "Справа вверху нажмите «Apple ID…» → «Войти».\n\n"
        "Откроется отдельное чёрное окно — так и должно быть.\n"
        "Введите:\n"
        "• свой Apple ID (почту),\n"
        "• пароль,\n"
        "• код из SMS или с другого устройства Apple.\n\n"
        "После успешного входа кнопка станет зелёной.\n"
        "Дальше: найдите приложение → скачайте → установите на телефон.",
    ),
    (
        "Важно знать",
        "Ставятся только приложения, которые уже были на вашем Apple ID "
        "(покупки или прошлые установки).\n\n"
        "Если Apple пишет, что нужна лицензия — этого приложения на аккаунте нет.\n"
        "Это ограничение магазина, а не поломка программы.",
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
        height=520,
    )


def show_setup_dialog(parent: QWidget | None = None) -> None:
    from ios_restore.ui.dependencies_dialog import show_dependencies_dialog

    show_dependencies_dialog(parent)


class OnboardingDialog(QDialog):
    """Multi-page first-run guide ending with ToS acceptance."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Знакомство с iCarcas")
        self.setMinimumSize(540, 460)
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
        offer_shortcut = (
            sys.platform == "win32"
            and desk.is_frozen()
            and desk.app_launch_target() is not None
        )
        self.shortcut_check = QCheckBox("Создать ярлык iCarcas на рабочем столе")
        self.shortcut_check.setChecked(offer_shortcut)
        self.shortcut_check.setVisible(offer_shortcut)
        layout.addWidget(self.shortcut_check)
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
        if self.shortcut_check.isVisible() and self.shortcut_check.isChecked():
            try:
                path = desk.create_desktop_shortcut()
                QMessageBox.information(
                    self,
                    "Ярлык",
                    f"Ярлык создан на рабочем столе:\n{path.name}",
                )
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "Ярлык",
                    f"Не удалось создать ярлык автоматически.\n{exc}",
                )
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
        return tos_accepted(settings) and onboarding_done(settings)
    return True
