"""Main window: device detection, App Store via interactive ipatool console, install."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ios_restore.application.diagnostics_service import DiagnosticsService
from ios_restore.application.system_health_service import SystemHealthService
from ios_restore.application.license_check_service import LicenseCheckService
from ios_restore.application.regional_search_service import RegionalAppSearchService
from ios_restore.application.smart_search_service import SmartAppSearchService
from ios_restore.domain.models import (
    AppReference,
    AppSearchResult,
    AppVersionInfo,
    CatalogApp,
    DeviceInfo,
    LicenseCheckResult,
    PackageInfo,
    PurchasedApp,
)
from ios_restore.domain.version_compare import device_meets_minimum
from ios_restore.infrastructure import keychain_passphrase as kc_pass
from ios_restore.infrastructure.apps_catalog import filter_catalog, load_apps_catalog
from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter
from ios_restore.infrastructure.device_cli_adapter import DeviceCliAdapter
from ios_restore.infrastructure.environment_cli_adapter import EnvironmentCliAdapter
from ios_restore.infrastructure.history_store import HistoryStore
from ios_restore.infrastructure.install_cli_adapter import InstallCliAdapter
from ios_restore.infrastructure.paths import default_packages_dir, default_tools_dir
from ios_restore.ui import apple_ui as aui
from ios_restore.ui.apple_ui import (
    AppleButton,
    FadeStack,
    Group,
    Page,
    ProgressLine,
    Row,
    Sidebar,
    Tile,
    Toggle,
)
from ios_restore.ui.brand_icon import load_app_icon
from ios_restore.ui.history_dialog import show_history_dialog, show_install_success_dialog
from ios_restore.application.dependency_service import DependencyService
from ios_restore.ui.dependencies_dialog import show_dependencies_dialog
from ios_restore.ui.system_doctor_dialog import show_system_doctor
from ios_restore.ui.onboarding import (
    ensure_onboarding,
    show_help_dialog,
)
from ios_restore.ui.release_notes import show_release_notes_dialog
from ios_restore.ui.theme import PALETTES, build_palette, repolish
from ios_restore.ui.tos import ensure_tos_accepted, tos_accepted
from ios_restore.ui.workers import (
    AuthInfoWorker,
    DetectDevicesWorker,
    InspectPackageWorker,
    InstallAppWorker,
    PairDeviceWorker,
    RegionalSearchAppWorker,
)


def _app_version() -> str:
    try:
        from importlib.metadata import version

        return version("ios-restore")
    except Exception:
        return "0.3.0"


class _FlowCard:
    """Совместимость со старыми вызовами card_*.set_state → плитки на «Начало»."""

    def __init__(self, tiles: dict[str, Tile], letter: str, status: QLabel | None = None) -> None:
        self._tiles = tiles
        self._letter = letter
        self._status = status

    def set_state(self, state: str, status_text: str = "") -> None:
        tile = self._tiles.get(self._letter)
        if tile is not None:
            tile.set_done(state == "done")
        if self._status is not None and status_text:
            self._status.setText(status_text)

def _dialog_qss(mode: str) -> str:
    """Modal table dialogs follow the active theme (no forced Windows-white)."""
    p = PALETTES[mode if mode in PALETTES else "dark"]
    return (
        f"* {{ background-color: {p['surface']}; color: {p['text']}; }}"
        f"QTableWidget {{ background-color: {p['surface2']}; color: {p['text']};"
        f" gridline-color: {p['border']}; border: 1px solid {p['border']};"
        f" border-radius: 10px; }}"
        f"QTableWidget::item {{ background-color: {p['surface2']}; color: {p['text']};"
        f" padding: 6px; }}"
        f"QTableWidget::item:selected {{ background-color: {p['accent']};"
        f" color: {p['accent_text']}; }}"
        f"QHeaderView::section {{ background-color: {p['surface']}; color: {p['muted']};"
        f" border: 1px solid {p['border']}; padding: 6px 8px; font-weight: 600; }}"
        f"QPushButton {{ background-color: {p['surface2']}; color: {p['text']};"
        f" border: 1px solid {p['border_strong']}; border-radius: 9px; padding: 8px 14px; }}"
        f"QPushButton:hover {{ background-color: {p['hover']}; border-color: {p['accent']}; }}"
        f"QCheckBox {{ color: {p['text']}; }}"
        f"QLabel {{ color: {p['text']}; }}"
        f"QLabel#selectionDetail {{ background-color: {p['surface2']};"
        f" border: 1px solid {p['border']}; border-radius: 10px; padding: 10px; }}"
        f"QLineEdit {{ background-color: {p['surface2']}; color: {p['text']};"
        f" border: 1px solid {p['border']}; border-radius: 9px; padding: 8px 10px; }}"
    )


_EMPTY_CELL = "—"


def _dialog_palette(mode: str) -> QPalette:
    return build_palette(mode if mode in PALETTES else "dark")


def _cell_text(value: str | None) -> str:
    text = (value or "").strip()
    return text if text else _EMPTY_CELL


def _fill_table_row(
    table: QTableWidget,
    row_idx: int,
    values: tuple[str, ...],
    *,
    data_index: int | None = None,
) -> None:
    for col_idx, value in enumerate(values):
        text = _cell_text(value)
        item = QTableWidgetItem(text)
        # Let dialog QSS / palette drive colors (no forced black-on-white).
        item.setToolTip(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if col_idx == 0 and data_index is not None:
            item.setData(Qt.ItemDataRole.UserRole, data_index)
        table.setItem(row_idx, col_idx, item)


def _selected_data_index(table: QTableWidget) -> int | None:
    row_idx = table.currentRow()
    if row_idx < 0:
        return None
    for col in range(min(2, table.columnCount())):
        item = table.item(row_idx, col)
        if item is None:
            continue
        raw = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(raw, int):
            return raw
    return row_idx


def _tune_data_table(
    table: QTableWidget,
    *,
    name_col: int = 0,
    hide_empty_columns: bool = True,
    wrap: bool = False,
) -> None:
    """Readable grid: one-line rows by default (wrap=True only when needed)."""
    table.setWordWrap(wrap)
    table.setTextElideMode(
        Qt.TextElideMode.ElideNone if wrap else Qt.TextElideMode.ElideRight
    )
    table.setAlternatingRowColors(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setSortingEnabled(True)
    table.verticalHeader().setVisible(True)
    table.verticalHeader().setDefaultSectionSize(28)
    table.verticalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.ResizeToContents
        if wrap
        else QHeaderView.ResizeMode.Fixed
    )

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setMinimumSectionSize(72)

    for col in range(table.columnCount()):
        if hide_empty_columns and _column_is_empty(table, col):
            table.setColumnHidden(col, True)
            continue
        table.setColumnHidden(col, False)
        if col == name_col:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

    if wrap:
        table.resizeRowsToContents()
    else:
        table.resizeColumnsToContents()
        # Keep name readable; avoid jagged columns from multi-line cells.
        if 0 <= name_col < table.columnCount() and not table.isColumnHidden(name_col):
            table.setColumnWidth(name_col, max(table.columnWidth(name_col), 260))
        for col in range(table.columnCount()):
            if col == name_col or table.isColumnHidden(col):
                continue
            table.setColumnWidth(col, min(max(table.columnWidth(col), 80), 220))
        for row in range(table.rowCount()):
            table.setRowHeight(row, 28)


def _column_is_empty(table: QTableWidget, col: int) -> bool:
    for row in range(table.rowCount()):
        item = table.item(row, col)
        text = (item.text() if item else "").strip()
        if text and text != _EMPTY_CELL:
            return False
    return table.rowCount() > 0


def _make_selection_detail(parent: QWidget) -> QLabel:
    detail = QLabel("Выберите строку — здесь будет полное название и ID.", parent)
    detail.setObjectName("selectionDetail")
    detail.setWordWrap(True)
    detail.setMinimumHeight(72)
    detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return detail


def make_button(text: str, variant: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if variant:
        button.setProperty("variant", variant)
    return button


class Card(QFrame):
    """Карточка с заголовком, статусом справа и необязательным номером шага."""

    def __init__(
        self,
        title: str,
        step: int | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("card")
        self._step = step

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 20)
        outer.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(12)
        self.badge: QLabel | None = None
        if step is not None:
            self.badge = QLabel(str(step))
            self.badge.setObjectName("stepBadge")
            self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.badge.setProperty("state", "idle")
            head.addWidget(self.badge)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("cardTitle")
        head.addWidget(title_lbl)
        head.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("cardStatus")
        head.addWidget(self.status)
        outer.addLayout(head)

        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setObjectName("hint")
            hint_lbl.setWordWrap(True)
            outer.addWidget(hint_lbl)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body)

    def set_state(self, state: str, status_text: str = "") -> None:
        """state: idle | active | done"""
        self.status.setText(status_text)
        if self.badge is not None:
            self.badge.setProperty("state", state)
            self.badge.setText("✓" if state == "done" else str(self._step))
            repolish(self.badge)


class Chip(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setProperty("state", "idle")
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

    def set_state(self, ok: bool, text: str) -> None:
        self.setText(text)
        self.setProperty("state", "ok" if ok else "idle")
        repolish(self)


def make_corner_button(text: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("cornerChip")
    button.setText(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    button.setProperty("state", "idle")
    return button


class MainWindow(QMainWindow):
    def __init__(
        self,
        packages_dir: Path | None = None,
        *,
        mode: str = "dark",
    ) -> None:
        super().__init__()
        self.setWindowTitle("iCarcas")
        self.setWindowIcon(load_app_icon())
        self.resize(980, 720)
        self.setMinimumSize(860, 600)

        self._thread_pool = QThreadPool.globalInstance()
        self._packages_dir = packages_dir or default_packages_dir()
        self._packages_dir.mkdir(parents=True, exist_ok=True)
        self._busy = False
        self._devices: list[DeviceInfo] = []
        self._package: PackageInfo | None = None
        self._mode = mode if mode in ("light", "dark") else "dark"
        tools = default_tools_dir()
        self._device_adapter = DeviceCliAdapter(tools_dir=tools)
        self._appstore = AppStoreCliAdapter(tools_dir=tools)
        self._installer = InstallCliAdapter(tools_dir=tools)
        self._smart_search = SmartAppSearchService()
        self._license_check = LicenseCheckService()
        self._history = HistoryStore(self._packages_dir / "icarcas-history.json")
        self._purchases_dump_path = self._appstore.purchases_dump_path(self._packages_dir)
        self._purchases_cache: list[PurchasedApp] | None = None
        self._account_storefront: str | None = None
        self._last_display_name: str | None = None
        self._bootstrap_scheduled = False
        self._device_ok = False
        self._trust_ok = False
        self._trust_error: str | None = None
        self._session_ok = False
        self._session_label: str | None = None
        self._versions_dump_path: Path | None = None
        self._catalog_cache: list[CatalogApp] | None = None
        self._download_poll: QTimer | None = None
        self._download_started_at: float | None = None
        self._download_last_bytes: int = 0
        self._download_last_bytes_at: float | None = None
        self._download_peak_bytes: int = 0

        aui.set_theme(self._mode)

        # Parent everything to this window — orphan QWidgets flash as tiny HWNDs on Windows.
        shell = QWidget(self)
        shell.setObjectName("root")
        self.setCentralWidget(shell)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        pages = [
            ("Начало", "start", "orange"),
            ("Устройство", "phone", "green"),
            ("Apple ID", "person", "blue"),
            ("Приложение", "app", "purple"),
            ("Журнал", "log", "gray"),
        ]
        self.sidebar = Sidebar(pages, f"v{_app_version()}", parent=shell)
        self.theme_toggle = Toggle(theme=True)
        self.theme_toggle.setToolTip("Светлая / тёмная тема")
        self.theme_toggle.toggled.connect(self._on_theme_toggled)
        self.sidebar.set_theme_toggle(self.theme_toggle)
        content = aui.styled(QWidget(shell), "content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.progress = ProgressLine(content)
        self.stack = FadeStack(content)
        content_layout.addWidget(self.progress)
        content_layout.addWidget(self.stack, 1)
        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(content, 1)

        self.tiles: dict[str, Tile] = {}
        # Always parent early: orphan QLabels become tiny top-level windows on Windows.
        self.flow_status = QLabel("", self)
        self.flow_status.setObjectName("footnote")
        self.chip_device = Chip("", self)
        self.chip_session = Chip("", self)
        self.chip_device.hide()
        self.chip_session.hide()
        self.stack.addWidget(self._build_page_start())
        self.stack.addWidget(self._build_page_device())
        self.stack.addWidget(self._build_page_store())
        self.stack.addWidget(self._build_page_app())
        self.stack.addWidget(self._build_page_log())
        self.sidebar.selected.connect(self.stack.go)

        # Aliases for busy toggles / older call sites.
        self.device_button = self.btn_find
        self.session_button = self.btn_login
        self.detect_button = self.btn_find
        self.pair_button = self.btn_trust
        self.login_button = self.btn_login
        self.auth_info_button = self.btn_check
        self.logout_button = self.btn_logout
        self.remember_pass_button = self.btn_save_pass
        self.clear_pass_button = self.btn_clear_pass
        self.open_help_button = self.help_button
        self.open_release_notes_button = self.release_notes_button
        self.card_store = _FlowCard(self.tiles, "B", self.flow_status)
        self.card_app = _FlowCard(self.tiles, "C", self.flow_status)

        self._sync_theme_toggle()
        self._refresh_passphrase_label()
        self.set_session_chip(self._appstore.session_files_present())
        self.set_device_chip(False)
        # Defer CLI / dependency probes until after first paint (avoids console flashes
        # while the brand splash is still running).
        # Env probe after first show — never during splash construction.

    def _wrap_scroll(self, page: Page) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        aui._clear_top_flash(page)  # noqa: SLF001
        return scroll

    def _build_page_start(self) -> QWidget:
        p = Page(
            "Начало работы",
            "Свои приложения из App Store на iPhone и iPad",
        )
        g = Group()
        steps = [
            ("A", "Подключите устройство", "USB-кабель, экран разблокирован", 1),
            ("B", "Войдите в Apple ID", "Пароль и 2FA в консоли ipatool", 2),
            ("C", "Выберите приложение", "Поиск ID, архив или bundle id", 3),
            ("D", "Установите на устройство", "Нужны сессия и готовый IPA", 3),
        ]
        for letter, title, sub, page_idx in steps:
            self.tiles[letter] = Tile("blue", letter)
            row = Row(title, sub, lead=self.tiles[letter])
            open_btn = AppleButton("Открыть", "plain")
            open_btn.clicked.connect(
                lambda _=False, i=page_idx: self.sidebar.select(i)
            )
            row.add_tail(open_btn)
            g.add(row)
        p.lay.addWidget(g)
        p.lay.addWidget(self.flow_status)

        help_g = Group()
        self.open_setup_button = AppleButton("Впервые здесь?")
        self.open_setup_button.setToolTip(
            "Первая подготовка компьютера: проверка и установка нужного одной кнопкой"
        )
        self.open_setup_button.clicked.connect(lambda: show_dependencies_dialog(self))
        r_setup = Row("Подготовка ПК", "Утилиты, драйверы, ipatool")
        r_setup.add_tail(self.open_setup_button)
        help_g.add(r_setup)

        self.doctor_button = AppleButton("Проверить систему", "plain")
        self.doctor_button.setToolTip(
            "Проверка компонентов, места на диске, подключения и сессии"
        )
        self.doctor_button.clicked.connect(self._on_system_doctor)
        doctor_row = Row(
            "System Doctor", "Причины проблем и рекомендации по исправлению"
        )
        doctor_row.add_tail(self.doctor_button)
        help_g.add(doctor_row)

        self.release_notes_button = AppleButton("Что нового", "plain")
        self.release_notes_button.clicked.connect(lambda: show_release_notes_dialog(self))
        r_notes = Row("Обновления", "Изменения с последнего релиза")
        r_notes.add_tail(self.release_notes_button)
        help_g.add(r_notes)

        self.help_button = AppleButton("Справка", "plain")
        self.help_button.clicked.connect(lambda: show_help_dialog(self))
        r_help = Row("Справка", "Как пользоваться — простые шаги")
        r_help.add_tail(self.help_button)
        help_g.add(r_help)

        self.replay_onboarding_button = AppleButton("Обучение", "plain")
        self.replay_onboarding_button.clicked.connect(self._on_replay_onboarding)
        r_onb = Row("Обучение", "Повторить знакомство")
        r_onb.add_tail(self.replay_onboarding_button)
        help_g.add(r_onb)

        self.shortcut_button = AppleButton("Ярлык", "plain")
        self.shortcut_button.clicked.connect(self._on_create_desktop_shortcut)
        r_short = Row("Ярлык", "На рабочий стол")
        r_short.add_tail(self.shortcut_button)
        help_g.add(r_short)
        p.lay.addWidget(help_g)

        self.privacy_label = QLabel(
            "Учётные данные и ключ сессии хранятся только на этом компьютере "
            "и никуда не передаются."
        )
        self.privacy_label.setObjectName("privacyNotice")
        self.privacy_label.setWordWrap(True)
        p.lay.addWidget(self.privacy_label)
        p.lay.addStretch(1)
        return self._wrap_scroll(p)

    def _build_page_device(self) -> QWidget:
        p = Page("Устройство", "Подключение iPhone или iPad к этому компьютеру")
        g = Group()
        self.row_device = Row("Устройство", "Не найдено", dot=True)
        self.btn_find = self.row_device.add_tail(AppleButton("Найти устройство"))
        self.btn_find.clicked.connect(self._on_detect)
        self.row_trust = Row(
            "Доверие к компьютеру",
            "Сначала найдите устройство",
            dot=True,
        )
        self.btn_trust = self.row_trust.add_tail(AppleButton("Установить доверие"))
        self.btn_trust.clicked.connect(self._on_pair)
        g.add(self.row_device)
        g.add(self.row_trust)
        p.lay.addWidget(g)
        p.lay.addStretch(1)
        return self._wrap_scroll(p)

    def _build_page_store(self) -> QWidget:
        p = Page("Apple ID", "Сессия App Store для загрузки ваших приложений")
        g = Group()
        self.row_session = Row("Сессия", "Не проверена", dot=True)
        self.btn_check = self.row_session.add_tail(AppleButton("Проверить…"))
        self.btn_check.clicked.connect(self._on_auth_info)

        self.row_login = Row("Вход", "Откроется консоль ipatool")
        self.btn_login = self.row_login.add_tail(AppleButton("Войти…", "filled"))
        self.btn_login.clicked.connect(self._on_login)

        self.row_logout = Row("Выход", "Завершить сессию ipatool")
        self.btn_logout = self.row_logout.add_tail(AppleButton("Выйти…", "danger"))
        self.btn_logout.clicked.connect(self._on_logout)

        r_pass = Row("Ключ сессии", "На этом компьютере")
        # Reuse Row subtitle label as passphrase status chip.
        self.passphrase_chip = r_pass.sub
        self.passphrase_chip.setObjectName("rowSub")
        self.btn_save_pass = AppleButton("Запомнить…", "plain")
        self.btn_save_pass.clicked.connect(self._on_save_passphrase)
        self.btn_clear_pass = AppleButton("Забыть", "plain")
        self.btn_clear_pass.clicked.connect(self._on_clear_passphrase)
        r_pass.add_tail(self.btn_save_pass)
        r_pass.add_tail(self.btn_clear_pass)

        for r in (self.row_session, self.row_login, self.row_logout, r_pass):
            g.add(r)
        p.lay.addWidget(g)

        arch = Group()
        r_arch = Row("Архив покупок", "Приложения с лицензией на этом Apple ID")
        self.archive_button = AppleButton("Архив…")
        self.archive_button.clicked.connect(self._on_archive_purchases)
        self.pickup_archive_button = AppleButton("Подхватить", "plain")
        self.pickup_archive_button.clicked.connect(self._on_pickup_purchases_dump)
        r_arch.add_tail(self.archive_button)
        r_arch.add_tail(self.pickup_archive_button)
        arch.add(r_arch)
        p.lay.addWidget(arch)

        note = QLabel(
            "Пароль, 2FA и Keychain passphrase вводятся только в консоли ipatool."
        )
        note.setObjectName("footnote")
        note.setWordWrap(True)
        p.lay.addWidget(note)
        p.lay.addStretch(1)
        return self._wrap_scroll(p)

    def _build_page_app(self) -> QWidget:
        p = Page("Приложение", "Поиск, загрузка IPA и установка на устройство")

        search_g = Group()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Название или коротко: МЭШ, Матч, Store ID, bundle…"
        )
        self.search_input.setClearButtonEnabled(True)
        search_g.add(self.search_input)

        self._region_code = "RU"
        self._region_tags: dict[str, QPushButton] = {}
        region_wrap = QWidget(p)
        region_grid = QGridLayout(region_wrap)
        region_grid.setContentsMargins(12, 8, 12, 8)
        region_grid.setHorizontalSpacing(6)
        region_grid.setVerticalSpacing(6)
        region_cols = 4
        for index, region in enumerate(RegionalAppSearchService.known_regions()):
            tag = QPushButton(region.name, region_wrap)
            tag.setObjectName("regionTag")
            tag.setCursor(Qt.CursorShape.PointingHandCursor)
            tag.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            tag.setToolTip(f"Регион App Store: {region.name} ({region.code})")
            tag.clicked.connect(
                lambda _checked=False, code=region.code: self._select_region(code)
            )
            self._region_tags[region.code] = tag
            region_grid.addWidget(tag, index // region_cols, index % region_cols)
        search_g.add(region_wrap)
        self._select_region("RU")

        r_find = Row("Поиск Store ID", "Скачивание — только при лицензии на аккаунте")
        self.regional_search_button = AppleButton("Найти ID…", "filled")
        self.regional_search_button.clicked.connect(self._on_regional_search_app)
        r_find.add_tail(self.regional_search_button)
        search_g.add(r_find)
        p.lay.addWidget(search_g)

        app_g = Group()
        self.app_input = QLineEdit()
        self.app_input.setPlaceholderText(
            "Bundle id (com.example.app) или App Store ID"
        )
        self.app_input.setClearButtonEnabled(True)
        app_g.add(self.app_input)

        self.try_purchase_check = QCheckBox(
            "Попробовать оформить лицензию в текущем регионе"
        )
        self.try_purchase_check.setToolTip(
            "Только если приложение доступно на витрине текущего Apple ID. "
            "Чужой регион не открывает."
        )
        check_wrap = QWidget()
        check_lay = QHBoxLayout(check_wrap)
        check_lay.setContentsMargins(16, 8, 16, 8)
        check_lay.addWidget(self.try_purchase_check)
        app_g.add(check_wrap)

        r_dl = Row("Загрузка", "Скачать IPA из вашей библиотеки")
        self.download_button = AppleButton("Скачать IPA…")
        self.download_button.clicked.connect(self._on_download)
        r_dl.add_tail(self.download_button)
        app_g.add(r_dl)

        r_pick = Row("Готовый файл", "Использовать уже скачанный IPA")
        self.pickup_button = AppleButton("Подхватить IPA", "plain")
        self.pickup_button.clicked.connect(self._on_pickup_ipa)
        self.history_button = AppleButton("История…", "plain")
        self.history_button.clicked.connect(self._on_open_history)
        r_pick.add_tail(self.pickup_button)
        r_pick.add_tail(self.history_button)
        app_g.add(r_pick)

        r_ver = Row("Версии и каталог", "list-versions и локальный список Store ID")
        self.versions_button = AppleButton("Версии…", "plain")
        self.versions_button.clicked.connect(self._on_list_versions)
        self.pickup_versions_button = AppleButton("Подхватить", "plain")
        self.pickup_versions_button.clicked.connect(self._on_pickup_versions)
        self.catalog_button = AppleButton("Каталог…", "plain")
        self.catalog_button.clicked.connect(self._on_open_catalog)
        r_ver.add_tail(self.versions_button)
        r_ver.add_tail(self.pickup_versions_button)
        r_ver.add_tail(self.catalog_button)
        app_g.add(r_ver)
        p.lay.addWidget(app_g)

        self.download_status_panel = QFrame()
        self.download_status_panel.setObjectName("downloadStatusPanel")
        self.download_status_panel.setProperty("phase", "idle")
        dl_status_layout = QVBoxLayout(self.download_status_panel)
        dl_status_layout.setContentsMargins(14, 12, 14, 12)
        dl_status_layout.setSpacing(6)
        self.download_state_title = QLabel("Загрузка не запущена")
        self.download_state_title.setObjectName("downloadStateTitle")
        self.download_state_title.setProperty("phase", "idle")
        dl_status_layout.addWidget(self.download_state_title)
        self.download_state_detail = QLabel(
            "После «Скачать IPA…» здесь будет видно: идёт ли закачка, "
            "сколько МБ и сколько времени прошло."
        )
        self.download_state_detail.setObjectName("downloadStateDetail")
        self.download_state_detail.setWordWrap(True)
        dl_status_layout.addWidget(self.download_state_detail)
        self.download_progress = QProgressBar()
        self.download_progress.setObjectName("downloadProgress")
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setTextVisible(True)
        self.download_progress.setFormat("%p%")
        dl_status_layout.addWidget(self.download_progress)
        self.download_progress_label = QLabel("")
        self.download_progress_label.setObjectName("downloadProgressLabel")
        self.download_progress_label.setWordWrap(True)
        dl_status_layout.addWidget(self.download_progress_label)
        p.lay.addWidget(self.download_status_panel)

        ctrl = Group()
        r_ctrl = Row("Управление загрузкой", "")
        self.cancel_download_button = AppleButton("Отменить", "danger")
        self.cancel_download_button.setEnabled(False)
        self.cancel_download_button.clicked.connect(self._on_cancel_download)
        self.diag_button = AppleButton("Диагностика…", "plain")
        self.diag_button.clicked.connect(self._on_export_diagnostics)
        r_ctrl.add_tail(self.cancel_download_button)
        r_ctrl.add_tail(self.diag_button)
        ctrl.add(r_ctrl)
        p.lay.addWidget(ctrl)

        self.install_button = AppleButton(
            "Установить на устройство", "filled", large=True
        )
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._on_install)
        p.lay.addWidget(self.install_button)
        p.lay.addStretch(1)
        return self._wrap_scroll(p)

    def _build_page_log(self) -> QWidget:
        p = Page("Журнал", "Вывод утилит и ipatool")
        self.btn_clear_log = AppleButton("Очистить", "plain")
        p.head_tail.addWidget(self.btn_clear_log)
        self.output = QPlainTextEdit()
        self.output.setObjectName("log")
        self.output.setReadOnly(True)
        self.btn_clear_log.clicked.connect(self.output.clear)
        p.lay.addWidget(self.output, 1)
        return p

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._bootstrap_scheduled:
            return
        self._bootstrap_scheduled = True
        QTimer.singleShot(0, self._append_env_status)
        QTimer.singleShot(0, self._bootstrap_tos_and_session)

    def _sync_theme_toggle(self) -> None:
        self.theme_toggle.blockSignals(True)
        self.theme_toggle.setChecked(self._mode == "dark")
        self.theme_toggle.blockSignals(False)

    def _on_theme_toggled(self, on: bool) -> None:
        self.apply_theme("dark" if on else "light")

    def apply_theme(self, mode: str) -> None:
        if mode not in ("light", "dark"):
            mode = "dark"
        self._mode = mode
        aui.set_theme(mode)
        app = QApplication.instance()
        if app is not None:
            # Fusion palette from theme.py keeps dialogs readable.
            if mode in PALETTES:
                app.setPalette(build_palette(mode))
            app.setStyleSheet(aui.qss())
        self.sidebar.retheme()
        self._sync_theme_toggle()
        for widget in self.findChildren(QWidget):
            widget.update()
            if widget.property("state") is not None:
                repolish(widget)
        QSettings("iCarcas", "iCarcas").setValue("theme", mode)

    def log(self, text: str) -> None:
        self.output.appendPlainText(text)

    def set_device_working(self, text: str) -> None:
        self.row_device.set_sub(text)
        if self.row_device.dot is not None:
            self.row_device.dot.set_state("busy")

    @staticmethod
    def _style_apple_button(button: AppleButton, text: str, kind: str) -> None:
        button.setText(text)
        button.kind = kind
        button.update()
        button.updateGeometry()

    def _refresh_device_actions(self) -> None:
        if self.row_trust.dot is None:
            return
        if self._device_ok and self._trust_ok:
            self.row_trust.set_sub("Готово")
            self.row_trust.dot.set_state("on")
            self.btn_trust.hide()
            self._style_apple_button(self.btn_find, "Обновить", "plain")
            return
        if self._device_ok:
            self.row_trust.set_sub(
                self._trust_error
                or "На устройстве нажмите «Доверять», затем эту кнопку"
            )
            self.row_trust.dot.set_state("off")
            self.btn_trust.show()
            self._style_apple_button(self.btn_trust, "Установить доверие", "filled")
            self._style_apple_button(self.btn_find, "Обновить", "plain")
            return
        self.row_trust.set_sub("Сначала найдите устройство")
        self.row_trust.dot.set_state("off")
        self.btn_trust.hide()
        self._style_apple_button(self.btn_find, "Найти устройство", "filled")

    def _refresh_session_actions(self) -> None:
        if self._session_ok:
            self.row_login.hide()
            self.row_logout.show()
            self.row_logout.set_sub("Завершить текущую сессию")
            self._style_apple_button(self.btn_logout, "Выйти…", "danger")
            self._style_apple_button(self.btn_check, "Проверить…", "plain")
        else:
            self.row_login.show()
            self.row_login.set_sub("Откроется консоль ipatool")
            self._style_apple_button(self.btn_login, "Войти…", "filled")
            self.row_logout.hide()
            self._style_apple_button(self.btn_check, "Проверить…", "plain")

    def set_device_chip(
        self,
        found: bool,
        name: str = "",
        *,
        trust_ok: bool | None = None,
        trust_error: str | None = None,
    ) -> None:
        self._device_ok = found
        if trust_error is not None:
            self._trust_error = trust_error or None
        if not found:
            self._trust_ok = False
            self._trust_error = None
        elif trust_ok is not None:
            self._trust_ok = trust_ok
            if trust_ok:
                self._trust_error = None
        if found and name:
            label = name
        elif found:
            label = "Подключено"
        else:
            label = "Не найдено"
        self.row_device.set_sub(label)
        if self.row_device.dot is not None:
            self.row_device.dot.set_state("on" if found else "off")
        self.chip_device.set_state(found, label)
        self._refresh_device_actions()
        if "A" in self.tiles:
            self.tiles["A"].set_done(found and self._trust_ok)
        if found and self._trust_ok:
            self.card_app.set_state("active")

    def set_session_chip(self, ok: bool, detail: str | None = None) -> None:
        if detail:
            self._session_label = detail
        if not ok:
            self._session_label = None
        self._session_ok = ok
        if ok:
            label = self._session_label or "Вход выполнен"
            if label.strip().casefold() in {"сессия ok", "сессияok", "ok"}:
                label = "Вход выполнен"
        else:
            label = "Нужен вход"
        self.row_session.set_sub(label)
        if self.row_session.dot is not None:
            self.row_session.dot.set_state("on" if ok else "off")
        self.chip_session.set_state(ok, label)
        self._refresh_passphrase_label()
        self._refresh_session_actions()
        if "B" in self.tiles:
            self.tiles["B"].set_done(ok)
        self.card_store.set_state("done" if ok else "active", "Готово" if ok else "")
        if ok:
            self.card_app.set_state("active")
        self.archive_button.setEnabled(ok)
        self.pickup_archive_button.setEnabled(ok)

    def _bootstrap_tos_and_session(self) -> None:
        if not ensure_onboarding(self):
            QMessageBox.information(
                self,
                "iCarcas",
                "Без прохождения знакомства и условий download/install недоступны.\n"
                "Откройте «Справка» или «Обучение».",
            )
        self._maybe_prompt_dependencies()
        self._refresh_passphrase_label()
        if self._appstore.session_files_present() and kc_pass.has_stored_passphrase():
            worker = AuthInfoWorker(self._appstore)
            worker.signals.finished.connect(self._on_auth_info_done)
            worker.signals.failed.connect(lambda _m: None)
            self._thread_pool.start(worker)

    def _maybe_prompt_dependencies(self) -> None:
        report = DependencyService().check()
        if report.all_ok:
            return
        names = ", ".join(c.title for c in report.missing[:5])
        more = "" if len(report.missing) <= 5 else "…"
        answer = QMessageBox.question(
            self,
            "Нужны компоненты",
            "На этом ПК не хватает того, без чего загрузка/устройство не заработают:\n"
            f"{names}{more}\n\n"
            "Открыть окно «Впервые здесь?» и установить одной кнопкой?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            show_dependencies_dialog(self)

    def _require_tos(self) -> bool:
        if tos_accepted():
            return True
        # Re-open onboarding (includes ToS) if user skipped / reset.
        return ensure_onboarding(self) and tos_accepted()

    def _on_replay_onboarding(self) -> None:
        from ios_restore.ui.onboarding import OnboardingDialog

        dialog = OnboardingDialog(self)
        dialog.exec()
        self._refresh_passphrase_label()

    def _on_create_desktop_shortcut(self) -> None:
        from ios_restore.infrastructure import desktop_shortcut as desk

        if sys.platform != "win32":
            QMessageBox.information(
                self,
                "Ярлык",
                "Ярлык на рабочий стол сейчас создаётся на Windows.",
            )
            return
        try:
            if not desk.is_frozen():
                # Dev-run: point at python -m if no exe — still useful to say how.
                QMessageBox.information(
                    self,
                    "Ярлык",
                    "Ярлык на рабочий стол создаётся для portable-сборки "
                    "(iCarcas.exe из ZIP). После распаковки Release снова "
                    "откройте программу и нажмите «Ярлык».",
                )
                return
            path = desk.create_desktop_shortcut(force=True)
        except OSError as exc:
            QMessageBox.warning(self, "Ярлык", str(exc))
            return
        QMessageBox.information(
            self,
            "Ярлык",
            f"Готово. На рабочем столе появился ярлык:\n{path}",
        )

    def _refresh_passphrase_label(self) -> None:
        if kc_pass.has_stored_passphrase():
            tip = (
                "Ключ сессии сохранён локально на этом компьютере "
                "(не пароль Apple ID, никуда не отправляется)."
            )
            self.passphrase_chip.setText("Ключ сохранён на этом ПК.")
        else:
            tip = (
                "Ключ сессии не сохранён — консоль спросит при необходимости. "
                "УЗ и ключ никуда не передаются."
            )
            self.passphrase_chip.setText("Ключ не сохранён — при необходимости спросит консоль.")
        if hasattr(self, "session_button"):
            base = "Вход в ваш Apple ID. Зелёный цвет — вы вошли."
            self.session_button.setToolTip(f"{base}\n{tip}")

    def _on_save_passphrase(self) -> None:
        if not self._require_tos():
            return
        text, ok = QInputDialog.getText(
            self,
            "Запомнить ключ",
            "Введите Keychain passphrase\n"
            "(НЕ пароль Apple ID). Только локально на этом ПК, никуда не отправляется:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not text.strip():
            return
        try:
            kc_pass.save_passphrase(text.strip())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Ключ", str(exc))
            return
        self._refresh_passphrase_label()
        QMessageBox.information(
            self,
            "Ключ",
            "Сохранено. Загрузки смогут идти с повторами без повторного ввода.",
        )

    def _on_clear_passphrase(self) -> None:
        kc_pass.clear_passphrase()
        self._refresh_passphrase_label()
        self.output.appendPlainText("Сохранённый ключ удалён.")

    def _on_cancel_download(self) -> None:
        if self._appstore.cancel_active_process():
            self.cancel_download_button.setEnabled(False)
            self._stop_download_poll()
            self._set_download_progress_ui(
                phase="idle",
                percent=0,
                title="Загрузка отменена",
                detail="Процесс остановлен. Можно запустить снова.",
                label="",
            )
            self.card_app.set_state("idle", "Отменено")
            self.output.appendPlainText("Загрузка отменена.")
        else:
            QMessageBox.information(self, "Отмена", "Активной загрузки нет.")

    def _on_export_diagnostics(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить диагностику",
            str(Path.cwd() / "icarcas-diagnostics.zip"),
            "ZIP (*.zip)",
        )
        if not path:
            return
        devices = [
            {
                "device_id": d.device_id,
                "display_name": d.display_name,
                "os_version": d.os_version,
                "available_for_operations": d.available_for_operations,
            }
            for d in self._devices
        ]
        svc = DiagnosticsService(
            packages_dir=self._packages_dir,
            session_present=self._appstore.session_files_present(),
            devices=devices,
            log_text=self.output.toPlainText(),
        )
        try:
            out = svc.build_zip(Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Диагностика", str(exc))
            return
        QMessageBox.information(self, "Диагностика", f"Сохранено:\n{out}")

    def _on_auth_info_done(self, info: object) -> None:
        assert isinstance(info, dict)
        email = str(info.get("email") or "")
        storefront = str(info.get("storefront") or "")
        self._account_storefront = storefront.upper() if storefront else self._account_storefront
        detail = "Вход выполнен"
        if email:
            detail = email
        if storefront:
            detail = f"{detail} · {storefront}"
        self.set_session_chip(True, detail)
        self.output.appendPlainText(
            "auth info: " + ", ".join(f"{k}={v}" for k, v in info.items())
        )
        self._set_busy(False)

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        sec = max(0, int(seconds))
        mins, rem = divmod(sec, 60)
        return f"{mins:02d}:{rem:02d}"

    def _set_download_panel_phase(self, phase: str) -> None:
        self.download_status_panel.setProperty("phase", phase)
        self.download_state_title.setProperty("phase", phase)
        repolish(self.download_status_panel)
        repolish(self.download_state_title)

    def _set_download_progress_ui(
        self,
        *,
        visible: bool = True,
        percent: int | None = None,
        indeterminate: bool = False,
        label: str = "",
        title: str | None = None,
        detail: str | None = None,
        phase: str = "idle",
    ) -> None:
        self.download_status_panel.setVisible(True)
        self._set_download_panel_phase(phase)
        if title is not None:
            self.download_state_title.setText(title)
        if detail is not None:
            self.download_state_detail.setText(detail)
        if label:
            self.download_progress_label.setText(label)
            self.download_progress_label.setVisible(True)
        elif not visible:
            self.download_progress_label.clear()

        if phase == "idle" and not indeterminate and percent is None:
            self.download_progress.setRange(0, 100)
            self.download_progress.setValue(0)
            self.download_progress.setFormat("—")
            return
        if indeterminate:
            self.download_progress.setRange(0, 0)
            self.download_progress.setFormat("идёт…")
            return
        self.download_progress.setRange(0, 100)
        value = max(0, min(100, int(percent or 0)))
        self.download_progress.setValue(value)
        self.download_progress.setFormat(f"{value}%")

    def _show_download_idle(self, detail: str | None = None) -> None:
        self._download_started_at = None
        self._download_last_bytes = 0
        self._download_last_bytes_at = None
        self._download_peak_bytes = 0
        self._set_download_progress_ui(
            phase="idle",
            title="Загрузка не запущена",
            detail=detail
            or "Нажмите «Скачать IPA…» — здесь появится живой статус.",
            label="",
            percent=0,
        )

    def _refresh_live_download_status(self, progress: dict | None) -> None:
        """Update panel while download process is still running."""
        now = time.time()
        started = self._download_started_at or now
        elapsed = now - started
        elapsed_txt = self._format_elapsed(elapsed)

        preferred = getattr(self, "_download_store_id", None)
        disk_bytes = self._appstore.measure_partial_download_bytes(
            self._packages_dir, store_id=preferred
        )
        file_bytes = int((progress or {}).get("bytes") or 0)
        bytes_done = max(disk_bytes, file_bytes, self._download_peak_bytes)
        if bytes_done > self._download_peak_bytes:
            self._download_peak_bytes = bytes_done

        expected = int((progress or {}).get("expectedBytes") or 0)
        attempt = int((progress or {}).get("attempt") or 0)
        max_attempts = int((progress or {}).get("maxAttempts") or 5)
        phase = str((progress or {}).get("phase") or "downloading")
        raw_msg = str((progress or {}).get("message") or "").strip()

        speed_txt = ""
        if self._download_last_bytes_at is not None and bytes_done > self._download_last_bytes:
            dt = max(0.2, now - self._download_last_bytes_at)
            speed = (bytes_done - self._download_last_bytes) / dt / (1024 * 1024)
            if speed >= 0.05:
                speed_txt = f" · {speed:.1f} МБ/с"
        if bytes_done != self._download_last_bytes:
            self._download_last_bytes = bytes_done
            self._download_last_bytes_at = now

        mb = bytes_done / (1024 * 1024)
        attempt_txt = f"попытка {attempt}/{max_attempts}" if attempt else "запуск"

        if phase == "retry_wait":
            self._set_download_progress_ui(
                phase="running",
                indeterminate=True,
                title="Пауза перед повтором",
                detail=raw_msg or "Сеть/504 — сейчас ждём и повторим автоматически.",
                label=f"Прошло {elapsed_txt} · {attempt_txt}",
            )
            return

        if bytes_done > 0:
            if expected > 0:
                pct = int(min(99, (bytes_done * 100) / expected))
                self._set_download_progress_ui(
                    phase="running",
                    percent=pct,
                    title="Идёт скачивание",
                    detail=(
                        f"Уже на диске: {mb:.1f} МБ из ~{expected / (1024 * 1024):.0f} МБ"
                        f"{speed_txt}. Полоска растёт — загрузка реальная."
                    ),
                    label=f"Прошло {elapsed_txt} · {attempt_txt}",
                )
            else:
                self._set_download_progress_ui(
                    phase="running",
                    indeterminate=True,
                    title="Идёт скачивание",
                    detail=(
                        f"Уже на диске: {mb:.1f} МБ{speed_txt}. "
                        "Размер заранее неизвестен — смотрите рост МБ."
                    ),
                    label=f"Прошло {elapsed_txt} · {attempt_txt}",
                )
            self.output.setPlainText(
                f"Идёт скачивание IPA.\n"
                f"Скачано: {mb:.1f} МБ{speed_txt}\n"
                f"Время: {elapsed_txt} · {attempt_txt}\n"
                "Можно «Отменить загрузку»."
            )
            return

        # 0 bytes: still waiting for Apple / license / first chunk
        wait_hint = (
            "Процесс запущен, но байты ещё не пишутся. "
            "ipatool часто молчит 1–3 минуты (лицензия/CDN). "
            "Если таймер тикает — загрузка жива."
        )
        if elapsed >= 90:
            wait_hint = (
                "Уже больше 1.5 мин без МБ на диске. Обычно это ожидание Apple "
                "или проверка лицензии. Подождите ещё или отмените и повторите."
            )
        self._set_download_progress_ui(
            phase="running",
            indeterminate=True,
            title="Ожидание Apple…",
            detail=wait_hint,
            label=f"Прошло {elapsed_txt} · {attempt_txt} · пока 0 МБ",
        )
        self.output.setPlainText(
            f"Загрузка запущена, ждём первые данные.\n"
            f"Время: {elapsed_txt} · {attempt_txt}\n"
            f"Скачано пока: 0 МБ\n\n"
            "Это нормально в начале. Когда появятся МБ — статус сменится на "
            "«Идёт скачивание»."
        )

    def _start_download_poll(self) -> None:
        self._stop_download_poll()
        self.cancel_download_button.setEnabled(True)
        self._download_started_at = time.time()
        self._download_last_bytes = 0
        self._download_last_bytes_at = self._download_started_at
        self._download_peak_bytes = 0
        self._set_download_progress_ui(
            phase="running",
            indeterminate=True,
            title="Загрузка запущена",
            detail="Стартуем ipatool. Через секунду здесь появится таймер и МБ.",
            label="Прошло 00:00",
        )
        timer = QTimer(self)
        timer.setInterval(500)
        timer.timeout.connect(self._poll_download_result)
        self._download_poll = timer
        timer.start()

    def _stop_download_poll(self) -> None:
        if self._download_poll is not None:
            self._download_poll.stop()
            self._download_poll.deleteLater()
            self._download_poll = None
        self.cancel_download_button.setEnabled(False)

    def _poll_download_result(self) -> None:
        progress = self._appstore.read_download_progress(self._packages_dir)
        result = self._appstore.read_download_result(self._packages_dir)
        running = self._appstore.active_process_running()
        if result is None:
            if running:
                self._refresh_live_download_status(progress)
            else:
                # Скрипт умер до download-result.json (раньше — синтаксическая ошибка PS).
                self._stop_download_poll()
                self.card_app.set_state("idle", "Сбой")
                self._set_download_progress_ui(
                    phase="error",
                    percent=0,
                    title="Загрузка оборвалась",
                    detail=(
                        "Фоновый скрипт завершился без результата. "
                        "Это не «тихая» успешная закачка. Нажмите «Скачать IPA…» ещё раз."
                    ),
                    label="",
                )
                self.output.setPlainText(
                    "Загрузка не выполнена: процесс завершился без download-result.json.\n"
                    "Повторите «Скачать IPA…». Если снова сразу сбой — «Диагностика…»."
                )
            return
        self._stop_download_poll()
        before = getattr(self, "_download_before_names", set())
        before_mtimes = getattr(self, "_download_before_mtimes", {})
        preferred = getattr(self, "_download_store_id", None)
        reused = bool(result.get("reused"))
        fresh = bool(result.get("fresh"))
        duration = result.get("durationSec")
        ipa_from_result = str(result.get("ipaPath") or "").strip()
        path = None
        if ipa_from_result:
            candidate = Path(ipa_from_result)
            if candidate.is_file() and candidate.stat().st_size > 1024:
                path = candidate
        if path is None and result.get("success"):
            # Только свежий файл после этой загрузки — без подхвата старого IPA.
            path = self._appstore.find_ipa_path(
                self._packages_dir,
                before_names=before,
                before_mtimes=before_mtimes,
                timeout_sec=2.0,
                preferred_store_id=preferred,
                require_fresh=not reused,
                allow_existing_fallback=bool(reused),
            )
        if result.get("success"):
            mb_note = ""
            if path is not None:
                mb_note = f" ({path.stat().st_size / (1024 * 1024):.1f} МБ)"
            if reused or (path is not None and not fresh and path.name in before):
                self._set_download_progress_ui(
                    phase="ok",
                    percent=100,
                    title="Файл уже был на диске",
                    detail=(
                        f"Повторно с Apple не скачивалось{mb_note}. "
                        "Это не новая закачка — можно ставить или удалить IPA и скачать снова."
                    ),
                    label=f"Попытка заняла {duration or '?'} с",
                )
                if path is not None:
                    stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime(
                        "%d.%m.%Y %H:%M:%S"
                    )
                    self.output.setPlainText(
                        "Это не новая закачка.\n"
                        f"Использован существующий файл: {path}\n"
                        f"Дата файла: {stamp}\n"
                        f"Длительность попытки: {duration or '?'} с\n"
                        "Чтобы качать заново — удалите этот .ipa из packages и повторите."
                    )
                    self._begin_inspect_ipa(path)
                else:
                    self.output.setPlainText(
                        "ipatool сообщил success, но свежий IPA не найден.\n"
                        "Нажмите «Подхватить IPA» для файла с диска."
                    )
                return
            self._set_download_progress_ui(
                phase="ok",
                percent=100,
                title="Скачивание завершено",
                detail=f"Новый IPA получен за {duration or '?'} с{mb_note}. Читаю пакет…",
                label="100%",
            )
            if path is not None:
                self._begin_inspect_ipa(path)
                return
            self.output.setPlainText(
                "Download success, но новый IPA не найден в packages. "
                "Нажмите «Подхватить IPA»."
            )
            return
        # Ошибка загрузки — никогда не маскируем старым IPA как успех.
        err = str(result.get("error") or "download failed")
        hint = AppStoreCliAdapter.explain_download_failure(err)
        self._set_download_progress_ui(
            phase="error",
            percent=0,
            title="Загрузка не удалась",
            detail=hint,
            label="",
        )
        self.card_app.set_state("idle", "Ошибка")
        existing = self._appstore.find_ipa_path(
            self._packages_dir,
            preferred_store_id=preferred,
            allow_existing_fallback=True,
        )
        extra = ""
        if existing is not None:
            extra = (
                f"\n\nНа диске уже лежит старый файл:\n{existing.name}\n"
                "Его можно «Подхватить IPA» без повторной загрузки."
            )
        self.output.setPlainText(f"Загрузка не удалась.\n{hint}\n\n{err[:1500]}{extra}")
        QMessageBox.warning(self, "Загрузка", hint + extra)

    def _append_env_status(self) -> None:
        from ios_restore.ui import first_run

        report = DependencyService().check()
        lines = [
            "Готово к работе." if report.all_ok else "Нужна подготовка компьютера.",
            "",
            first_run.first_connection_steps(),
            "",
        ]
        if not report.all_ok:
            lines.append("Не хватает компонентов — «Впервые здесь?» → «Установить недостающее».")
            for comp in report.components:
                if not comp.ok:
                    lines.append(f"  • {comp.title}")
        else:
            lines.append("Компоненты на месте. Файлы IPA — в папке packages.")
        self.output.setPlainText("\n".join(lines))
        try:
            EnvironmentCliAdapter().check_tools()
        except Exception:  # noqa: BLE001
            pass

    def _on_detect(self) -> None:
        if self._busy:
            return
        self.set_device_working("Ищем…")
        self._set_busy(
            True,
            "Ищем устройство…\nПодключите кабель USB, разблокируйте экран и нажмите «Доверять».",
        )
        worker = DetectDevicesWorker(self._device_adapter)
        worker.signals.finished.connect(self._on_devices_found)
        worker.signals.failed.connect(self._on_device_worker_failed)
        self._thread_pool.start(worker)

    def _on_pair(self) -> None:
        if self._busy:
            return
        if not self._devices:
            QMessageBox.information(
                self,
                "Нет устройства",
                "Сначала нажмите «Устройство…» → «Найти устройство».",
            )
            return
        device = self._devices[0]
        QMessageBox.information(
            self,
            "Доверие",
            "Разблокируйте устройство. Если появится запрос — нажмите «Доверять».",
        )
        self.set_device_working("Связь…")
        self._set_busy(True, "Устанавливаем связь с устройством…")
        worker = PairDeviceWorker(self._device_adapter, device.device_id)
        worker.signals.finished.connect(self._on_paired)
        worker.signals.failed.connect(self._on_device_worker_failed)
        self._thread_pool.start(worker)

    def _on_login(self) -> None:
        if not self._require_tos():
            return
        try:
            self._appstore.begin_interactive_login()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Авторизация", str(exc))
            return
        # Подсказки только в журнале — без модалки, которая блокирует UI.
        self.output.setPlainText(
            "Открыта консоль входа.\n"
            "Введите Apple ID, пароль, ключ сессии и 2FA.\n"
            "После success → «Проверить сессию…», при желании «Запомнить ключ…»."
        )

    def _on_auth_info(self) -> None:
        if kc_pass.has_stored_passphrase():
            self._set_busy(True, "Читаю auth info…")
            worker = AuthInfoWorker(self._appstore)
            worker.signals.finished.connect(self._on_auth_info_done)
            worker.signals.failed.connect(self._on_worker_failed)
            self._thread_pool.start(worker)
            return
        try:
            self._appstore.begin_interactive_auth_info()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Сессия", str(exc))
            return
        present = self._appstore.session_files_present()
        self.set_session_chip(present)
        self.output.setPlainText(
            "Открыта консоль проверки сессии.\n"
            "Введите ключ (НЕ пароль Apple ID) и закройте консоль после success.\n"
            "Чтобы без консоли — «Запомнить ключ…».\n"
            f"Локальные файлы сессии: {'да' if present else 'нет'}."
        )

    def _on_logout(self) -> None:
        answer = QMessageBox.question(
            self,
            "Выход",
            "Открыть консоль ipatool auth revoke и удалить локальную сессию?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._appstore.begin_interactive_revoke()
        except Exception as exc:  # noqa: BLE001
            self.output.setPlainText(str(exc))
            return
        self.set_session_chip(False)
        self.output.setPlainText(
            "Открыта консоль auth revoke. "
            "Завершите её и при необходимости введите passphrase."
        )

    def _on_archive_purchases(self) -> None:
        if self._busy:
            return
        if not self._require_tos():
            return
        if not self._appstore.session_files_present():
            QMessageBox.information(
                self,
                "Архив покупок",
                "Сначала войдите в App Store (кнопка «Войти…»), "
                "чтобы ipatool видел покупки этого Apple ID.",
            )
            return
        pass_note = (
            "Будет использован сохранённый passphrase."
            if kc_pass.has_stored_passphrase()
            else "В консоли введите Keychain passphrase."
        )
        answer = QMessageBox.question(
            self,
            "Архив покупок",
            "Открыть дамп покупок?\n\n"
            f"{pass_note}\n"
            f"Результат: {self._purchases_dump_path}\n\n"
            "После DONE нажмите «Подхватить архив».",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._purchases_dump_path = self._appstore.begin_interactive_list_purchases(
                self._packages_dir
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Архив покупок", str(exc))
            return
        self.output.setPlainText(
            "Консоль дампа покупок открыта.\n"
            "1) Введите Keychain passphrase\n"
            "2) Дождитесь Saved … DONE\n"
            "3) Нажмите «Подхватить архив»\n\n"
            "Сценарий 1: в архиве — приложения, на которые есть лицензия "
            "у текущего Apple ID (в т.ч. купленные в другом регионе раньше)."
        )

    def _on_pickup_purchases_dump(self) -> None:
        try:
            purchases = self._appstore.load_purchases_dump(self._purchases_dump_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Архив покупок", str(exc))
            return
        if not purchases:
            QMessageBox.information(
                self, "Архив покупок", "В дампе приложений не найдено."
            )
            return
        self._purchases_cache = purchases
        self._show_purchases_dialog(purchases)

    def _load_purchases_cache(self) -> list[PurchasedApp]:
        if self._purchases_cache is not None:
            return self._purchases_cache
        path = Path(self._purchases_dump_path)
        if not path.is_file():
            return []
        try:
            purchases = self._appstore.load_purchases_dump(path)
        except Exception:  # noqa: BLE001
            return []
        self._purchases_cache = purchases
        return purchases

    def _check_license_for_app(
        self,
        *,
        store_id: str | None,
        bundle_id: str | None,
        app_region: str | None = None,
    ) -> LicenseCheckResult:
        return self._license_check.check(
            store_id=store_id,
            bundle_id=bundle_id,
            app_region=app_region,
            purchases=self._load_purchases_cache(),
            account_storefront=self._account_storefront,
        )

    def _on_system_doctor(self) -> None:
        service = SystemHealthService(
            packages_dir=self._packages_dir,
            device_adapter=self._device_adapter,
            session_present=self._appstore.session_files_present(),
        )
        show_system_doctor(self, service)

    def _on_open_history(self) -> None:
        entries = self._history.list_entries()
        if not entries:
            QMessageBox.information(
                self,
                "История",
                "Пока пусто — появится после скачивания или установки IPA.",
            )
            return
        entry = show_history_dialog(
            self,
            entries=entries,
            dialog_qss=_dialog_qss(self._mode),
        )
        if entry is None or not entry.ipa_path:
            return
        if entry.store_id:
            self.app_input.setText(entry.store_id)
        elif entry.bundle_id:
            self.app_input.setText(entry.bundle_id)
        self._last_display_name = entry.display_name
        self._begin_inspect_ipa(Path(entry.ipa_path))

    def _show_purchases_dialog(self, purchases: list[PurchasedApp]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Архив покупок ({len(purchases)})")
        dialog.resize(980, 560)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setStyleSheet(_dialog_qss(self._mode))
        pal = _dialog_palette(self._mode)
        dialog.setPalette(pal)

        layout = QVBoxLayout(dialog)
        hint = QLabel(
            "Это покупки текущего Apple ID. Выберите строку и нажмите «Скачать» — "
            "откроется консоль ipatool download. Названия не обрезаются."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        table = QTableWidget(len(purchases), 5, dialog)
        table.setPalette(pal)
        table.setAutoFillBackground(True)
        table.setHorizontalHeaderLabels(
            ["Название", "Bundle ID", "Store ID", "Версия", "Цена"]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        for row_idx, app in enumerate(purchases):
            _fill_table_row(
                table,
                row_idx,
                (
                    app.display_name or "",
                    app.bundle_id or "",
                    app.store_id or "",
                    app.version or "",
                    app.price or "",
                ),
                data_index=row_idx,
            )
        _tune_data_table(table, name_col=0)
        layout.addWidget(table)
        detail = _make_selection_detail(dialog)
        layout.addWidget(detail)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        use_btn = buttons.addButton(
            "Подставить ID", QDialogButtonBox.ButtonRole.ActionRole
        )
        dl_btn = buttons.addButton(
            "Скачать…", QDialogButtonBox.ButtonRole.AcceptRole
        )
        layout.addWidget(buttons)

        def _selected_app(*, quiet: bool = False) -> PurchasedApp | None:
            data_idx = _selected_data_index(table)
            if data_idx is None or not (0 <= data_idx < len(purchases)):
                if not quiet:
                    QMessageBox.information(
                        dialog, "Выбор", "Выберите приложение в списке."
                    )
                return None
            return purchases[data_idx]

        def _on_sel() -> None:
            app = _selected_app(quiet=True)
            if app is None:
                detail.setText("Выберите строку — здесь будет полное название и ID.")
                return
            detail.setText(
                f"{app.display_name or '—'}\n"
                f"Store ID: {app.store_id or '—'}\n"
                f"Bundle: {app.bundle_id or '—'}"
            )

        table.itemSelectionChanged.connect(_on_sel)

        def on_use() -> None:
            app = _selected_app()
            if app is None:
                return
            self._apply_app_reference(app.store_id, app.bundle_id)
            dialog.accept()
            self.output.setPlainText(
                f"Выбрано из архива: {app.display_name or '—'}\n"
                f"ID подставлен в поле приложения."
            )

        def on_download() -> None:
            app = _selected_app()
            if app is None:
                return
            self._apply_app_reference(app.store_id, app.bundle_id)
            dialog.accept()
            self._start_download(
                self._parse_app_reference(
                    (app.store_id or app.bundle_id or "").strip()
                ),
                confirm=False,
            )

        use_btn.clicked.connect(on_use)
        dl_btn.clicked.connect(on_download)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def _apply_app_reference(
        self,
        store_id: str | None,
        bundle_id: str | None,
    ) -> None:
        if store_id and store_id not in {"", "—"}:
            self.app_input.setText(store_id)
        elif bundle_id and bundle_id not in {"", "—"}:
            self.app_input.setText(bundle_id)

    def _on_regional_search_app(self) -> None:
        if self._busy:
            return
        term = self.search_input.text().strip()
        if not term:
            QMessageBox.information(self, "Поиск", "Введите название приложения для поиска.")
            return
        region_code = self._region_code
        if not region_code:
            QMessageBox.information(self, "Поиск", "Выберите регион App Store.")
            return
        self._set_busy(True, f"Умный поиск «{term}» ({region_code})…")
        worker = RegionalSearchAppWorker(self._smart_search, term, str(region_code))
        worker.signals.finished.connect(self._on_regional_search_results)
        worker.signals.failed.connect(self._on_worker_failed)
        self._thread_pool.start(worker)

    def _select_region(self, code: str) -> None:
        self._region_code = code
        for tag_code, tag in self._region_tags.items():
            selected = tag_code == code
            tag.setProperty("state", "ok" if selected else "idle")
            repolish(tag)

    def _on_regional_search_results(self, results: object) -> None:
        assert isinstance(results, list)
        self._set_busy(False)
        region_code = self._region_code
        if not results:
            QMessageBox.information(
                self,
                "Поиск",
                f"Приложений по запросу «{self.search_input.text().strip()}» "
                f"в регионе {region_code} не найдено.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Поиск ID ({region_code}) — {len(results)}")
        dialog.resize(1080, 680)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setStyleSheet(_dialog_qss(self._mode))
        pal = _dialog_palette(self._mode)
        dialog.setPalette(pal)

        layout = QVBoxLayout(dialog)
        hint = QLabel(
            f"Каталог + iTunes ({region_code}). "
            "Сверху — наиболее похожие по названию. "
            "Полное имя выбранного — в карточке ниже."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        category_filter = QComboBox(dialog)
        category_filter.addItem("Все категории")
        categories = sorted({
            app.category.strip()
            for app in results
            if app.category and app.category.strip()
        })
        category_filter.addItems(categories)
        category_filter.setToolTip(
            "Фильтр по категориям, полученным из App Store. "
            "У записей каталога категория может отсутствовать."
        )
        layout.addWidget(category_filter)

        table = QTableWidget(len(results), 8, dialog)
        table.setPalette(pal)
        table.setAutoFillBackground(True)
        table.setHorizontalHeaderLabels(
            [
                "Название", "Store ID", "Источник", "Bundle ID",
                "Версия", "Цена", "Категория", "Seller",
            ]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        for row_idx, app in enumerate(results):
            assert isinstance(app, AppSearchResult)
            _fill_table_row(
                table,
                row_idx,
                (
                    app.display_name or "",
                    app.store_id or "",
                    app.source or "",
                    app.bundle_id or "",
                    app.version or "",
                    app.price or "",
                    app.category or "",
                    app.seller_name or "",
                ),
                data_index=row_idx,
            )
        _tune_data_table(table, name_col=0, hide_empty_columns=True, wrap=False)

        def apply_category_filter(text: str) -> None:
            for row in range(table.rowCount()):
                category_item = table.item(row, 6)
                category = category_item.text() if category_item else ""
                table.setRowHidden(
                    row, text != "Все категории" and category != text
                )
            if text != "Все категории":
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        table.selectRow(row)
                        break
                else:
                    table.clearSelection()

        category_filter.currentTextChanged.connect(apply_category_filter)
        layout.addWidget(table)

        card_text = _make_selection_detail(dialog)
        card_text.setText("Выберите строку — карточка приложения.")
        layout.addWidget(card_text)
        license_lbl = QLabel("")
        license_lbl.setWordWrap(True)
        license_lbl.setObjectName("selectionDetail")
        layout.addWidget(license_lbl)

        try_purchase = QCheckBox(
            "Попробовать --purchase (только текущий storefront, не чужой регион)"
        )
        layout.addWidget(try_purchase)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        use_btn = buttons.addButton(
            "Подставить ID", QDialogButtonBox.ButtonRole.ActionRole
        )
        dl_btn = buttons.addButton(
            "Скачать на текущий Apple ID…", QDialogButtonBox.ButtonRole.AcceptRole
        )
        layout.addWidget(buttons)

        def _selected(*, quiet: bool = False) -> AppSearchResult | None:
            data_idx = _selected_data_index(table)
            if (
                data_idx is None
                or not (0 <= data_idx < len(results))
                or table.currentRow() < 0
                or table.isRowHidden(table.currentRow())
            ):
                if not quiet:
                    QMessageBox.information(
                        dialog, "Выбор", "Выберите приложение в списке."
                    )
                return None
            app = results[data_idx]
            assert isinstance(app, AppSearchResult)
            return app

        def _apply_card(app: AppSearchResult, license_result: LicenseCheckResult) -> None:
            card_text.setText(
                f"{app.display_name or '—'}\n"
                f"Store ID: {app.store_id or '—'} · "
                f"Регион: {app.region or region_code}\n"
                f"Bundle: {app.bundle_id or '—'}\n"
                f"Источник: {app.source or '—'} · "
                f"Seller: {app.seller_name or '—'} · "
                f"Версия: {app.version or '—'} · "
                f"Категория: {app.category or 'не указана'} · "
                f"Цена: {app.price or 'неизвестна'}"
            )
            status_map = {
                "licensed": "Лицензия: похоже, есть",
                "not_found": "Лицензия: в архиве покупок не найдена",
                "region_mismatch": "Лицензия: конфликт региона витрины",
                "unknown": "Лицензия: неизвестно (нет архива покупок)",
            }
            license_lbl.setText(
                f"{status_map.get(license_result.status, 'Лицензия')}\n"
                f"{license_result.message}"
            )

        def _on_sel() -> None:
            app = _selected(quiet=True)
            if app is None:
                card_text.setText("Выберите строку — карточка приложения.")
                license_lbl.clear()
                return
            lic = self._license_check.check_search_result(
                app,
                purchases=self._load_purchases_cache(),
                account_storefront=self._account_storefront,
            )
            _apply_card(app, lic)

        table.itemSelectionChanged.connect(_on_sel)

        def on_use() -> None:
            app = _selected()
            if app is None:
                return
            self._apply_app_reference(app.store_id, app.bundle_id)
            self._last_display_name = app.display_name
            self.search_input.clear()
            dialog.accept()
            lic = self._license_check.check_search_result(
                app,
                purchases=self._load_purchases_cache(),
                account_storefront=self._account_storefront,
            )
            self.output.setPlainText(
                f"ID из региона {region_code}: {app.display_name or '—'}\n"
                f"{lic.message}\n"
                + AppStoreCliAdapter.explain_download_failure("license")
            )

        def on_download() -> None:
            app = _selected()
            if app is None:
                return
            if not (app.store_id or app.bundle_id):
                QMessageBox.warning(dialog, "Скачать", "У записи нет Store ID / bundle.")
                return
            self._apply_app_reference(app.store_id, app.bundle_id)
            self._last_display_name = app.display_name
            self.try_purchase_check.setChecked(try_purchase.isChecked())
            self.search_input.clear()
            dialog.accept()
            ref = (
                AppReference(store_id=app.store_id, display_name=app.display_name)
                if app.store_id
                else AppReference(bundle_id=app.bundle_id, display_name=app.display_name)
            )
            self._start_download(
                ref,
                confirm=True,
                app_region=app.region or str(region_code),
            )

        use_btn.clicked.connect(on_use)
        dl_btn.clicked.connect(on_download)
        buttons.rejected.connect(dialog.reject)
        if results:
            table.selectRow(0)
            _on_sel()
        dialog.exec()

    def _on_download(self) -> None:
        raw = self.app_input.text().strip()
        if not raw:
            QMessageBox.information(self, "Приложение", "Укажите bundle id или App Store ID.")
            return
        self._start_download(self._parse_app_reference(raw), confirm=True)

    def _start_download(
        self,
        app: AppReference,
        *,
        confirm: bool,
        external_version_id: str | None = None,
        app_region: str | None = None,
    ) -> None:
        if not self._require_tos():
            return
        try_purchase = self.try_purchase_check.isChecked()
        target = app.display_name or app.bundle_id or app.store_id or "?"
        version_line = (
            f"версия (external-version-id): {external_version_id}\n"
            if external_version_id
            else "версия: latest\n"
        )
        headless = kc_pass.has_stored_passphrase()
        mode_line = (
            "Режим: фоновая загрузка с ретраями (сохранённый passphrase).\n"
            if headless
            else "Режим: консоль ipatool (введите passphrase вручную).\n"
        )
        license_result = self._check_license_for_app(
            store_id=app.store_id,
            bundle_id=app.bundle_id,
            app_region=app_region,
        )
        license_line = f"Лицензия: {license_result.message}\n"
        msg = (
            "Начать download IPA?\n"
            f"{target}\n"
            f"ID: {app.store_id or app.bundle_id}\n"
            f"{version_line}"
            f"{mode_line}"
            f"{license_line}"
            f"Каталог: {self._packages_dir}\n"
            f"--purchase: {'да (текущий storefront)' if try_purchase else 'нет'}\n"
        )
        if license_result.status == "not_found" and not try_purchase:
            msg += "\nВ архиве покупок ID не найден — загрузка, скорее всего, упадёт."
        if license_result.status == "region_mismatch":
            msg += "\nРегион витрины не совпадает — высокий риск отказа."
        if confirm:
            answer = QMessageBox.question(self, "Загрузка", msg)
            if answer != QMessageBox.StandardButton.Yes:
                return
        if app.display_name:
            self._last_display_name = app.display_name
        before_mtimes = self._appstore.list_ipa_mtimes(self._packages_dir)
        try:
            self._appstore.begin_interactive_download(
                app,
                str(self._packages_dir),
                try_purchase=try_purchase,
                external_version_id=external_version_id,
            )
        except Exception as exc:  # noqa: BLE001
            hint = AppStoreCliAdapter.explain_download_failure(str(exc))
            QMessageBox.warning(self, "Загрузка", f"{exc}\n\n{hint}")
            return
        self._download_before_names = set(before_mtimes.keys())
        self._download_before_mtimes = before_mtimes
        self._download_store_id = (app.store_id or "").strip() or None
        self.card_app.set_state("active", "Загрузка…")
        if headless:
            existing_note = ""
            sid = self._download_store_id
            if sid and any(n.startswith(f"{sid}_") for n in before_mtimes):
                existing_note = (
                    "\nНа диске уже есть IPA с этим ID — если прогресс "
                    "сразу 100%, файл могли не перекачать заново.\n"
                )
            self.output.setPlainText(
                "Фоновая загрузка запущена.\n"
                "Смотрите прогресс-бар в блоке «Приложение».\n"
                "Дождитесь 100% / авто-подхвата или «Отменить загрузку»."
                + existing_note
                + "\n"
                + AppStoreCliAdapter.explain_download_failure("license")
            )
            self._start_download_poll()
        else:
            self.output.setPlainText(
                "Консоль download открыта.\n"
                "1) Keychain passphrase\n"
                "2) success / DONE\n"
                "3) «Подхватить IPA»\n\n"
                + AppStoreCliAdapter.explain_download_failure("license")
            )

    def _on_list_versions(self) -> None:
        raw = self.app_input.text().strip()
        if not raw.isdigit():
            QMessageBox.information(
                self,
                "Версии",
                "Для списка версий укажите числовой App Store ID "
                "(не bundle id). Можно взять из архива, регионального поиска "
                "или каталога ID.",
            )
            return
        if not self._appstore.session_files_present():
            QMessageBox.information(
                self,
                "Версии",
                "Нужна активная сессия App Store. Сначала «Войти…».",
            )
            return
        answer = QMessageBox.question(
            self,
            "Версии",
            f"Открыть консоль list-versions для ID {raw}?\n"
            "Passphrase в консоли → дамп ID версий "
            "(метаданные для ~40 новейших) → «Подхватить версии».",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path = self._appstore.begin_interactive_list_versions(
                raw, self._packages_dir
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Версии", str(exc))
            return
        self._versions_dump_path = path
        self.output.setPlainText(
            f"Консоль list-versions открыта.\n"
            f"Дамп: {path}\n"
            "1) Passphrase в консоли\n"
            "2) Дождитесь DONE\n"
            "3) «Подхватить версии»"
        )

    def _on_pickup_versions(self) -> None:
        path = self._versions_dump_path
        if path is None:
            raw = self.app_input.text().strip()
            if raw.isdigit():
                path = self._appstore.versions_dump_path(self._packages_dir, raw)
        if path is None:
            QMessageBox.information(
                self,
                "Версии",
                "Сначала «Версии…» для нужного Store ID, "
                "либо укажите ID в поле приложения.",
            )
            return
        try:
            versions = self._appstore.load_versions_dump(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Версии", str(exc))
            return
        store_id = path.stem.removeprefix("versions-")
        self._show_versions_dialog(store_id, versions)

    def _show_versions_dialog(
        self, store_id: str, versions: list[AppVersionInfo]
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Версии ({store_id}) — {len(versions)}")
        dialog.resize(900, 560)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setStyleSheet(_dialog_qss(self._mode))
        pal = _dialog_palette(self._mode)
        dialog.setPalette(pal)

        layout = QVBoxLayout(dialog)
        hint = QLabel(
            "Выберите версию и «Скачать». Нужна лицензия на текущем Apple ID. "
            "Старые сборки иногда уже не подписываются Apple."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        table = QTableWidget(len(versions), 3, dialog)
        table.setPalette(pal)
        table.setAutoFillBackground(True)
        table.setHorizontalHeaderLabels(
            ["External version ID", "Display version", "Release date"]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        for row_idx, ver in enumerate(versions):
            _fill_table_row(
                table,
                row_idx,
                (
                    ver.external_version_id,
                    ver.display_version or "",
                    ver.release_date or "",
                ),
                data_index=row_idx,
            )
        _tune_data_table(table, name_col=0, hide_empty_columns=True)
        layout.addWidget(table)
        detail = _make_selection_detail(dialog)
        layout.addWidget(detail)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        dl_btn = buttons.addButton(
            "Скачать эту версию…", QDialogButtonBox.ButtonRole.AcceptRole
        )
        layout.addWidget(buttons)

        def _on_sel() -> None:
            data_idx = _selected_data_index(table)
            if data_idx is None or not (0 <= data_idx < len(versions)):
                detail.setText("Выберите строку — здесь будут полные поля версии.")
                return
            ver = versions[data_idx]
            detail.setText(
                f"external-version-id: {ver.external_version_id}\n"
                f"display: {ver.display_version or '—'}\n"
                f"release: {ver.release_date or '—'}"
            )

        def on_download() -> None:
            data_idx = _selected_data_index(table)
            if data_idx is None or not (0 <= data_idx < len(versions)):
                QMessageBox.information(dialog, "Выбор", "Выберите версию.")
                return
            ver = versions[data_idx]
            self.app_input.setText(store_id)
            dialog.accept()
            self._start_download(
                AppReference(store_id=store_id),
                confirm=True,
                external_version_id=ver.external_version_id,
            )

        table.itemSelectionChanged.connect(_on_sel)
        dl_btn.clicked.connect(on_download)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def _on_open_catalog(self) -> None:
        try:
            if self._catalog_cache is None:
                self._catalog_cache = load_apps_catalog()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Каталог ID", str(exc))
            return
        self._show_catalog_dialog(self._catalog_cache)

    def _show_catalog_dialog(self, apps: list[CatalogApp]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Каталог ID ({len(apps)})")
        dialog.resize(980, 620)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setStyleSheet(_dialog_qss(self._mode))
        pal = _dialog_palette(self._mode)
        dialog.setPalette(pal)

        layout = QVBoxLayout(dialog)
        hint = QLabel(
            "Локальный список Store ID. Полные названия без обрезки. "
            "Скачивание — только при лицензии на текущем Apple ID. "
            "Мультивыбор → «Массовая загрузка»."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        search = QLineEdit(dialog)
        search.setPlaceholderText("Фильтр по названию или ID…")
        search.setClearButtonEnabled(True)
        layout.addWidget(search)

        table = QTableWidget(0, 2, dialog)
        table.setPalette(pal)
        table.setAutoFillBackground(True)
        table.setHorizontalHeaderLabels(["Название", "Store ID"])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(table)
        detail = _make_selection_detail(dialog)
        layout.addWidget(detail)

        filtered: list[CatalogApp] = list(apps)

        def refill(rows: list[CatalogApp]) -> None:
            nonlocal filtered
            filtered = rows
            table.setSortingEnabled(False)
            table.setRowCount(len(rows))
            for row_idx, app in enumerate(rows):
                _fill_table_row(
                    table,
                    row_idx,
                    (app.display_name, app.store_id),
                    data_index=row_idx,
                )
            _tune_data_table(table, name_col=0, hide_empty_columns=False)

        def on_filter(text: str) -> None:
            refill(filter_catalog(apps, text))

        search.textChanged.connect(on_filter)
        refill(apps)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        use_btn = buttons.addButton(
            "Подставить ID", QDialogButtonBox.ButtonRole.ActionRole
        )
        dl_btn = buttons.addButton(
            "Скачать…", QDialogButtonBox.ButtonRole.ActionRole
        )
        bulk_btn = buttons.addButton(
            "Массовая загрузка…", QDialogButtonBox.ButtonRole.AcceptRole
        )
        layout.addWidget(buttons)

        def _selected() -> list[CatalogApp]:
            picked: list[CatalogApp] = []
            seen: set[int] = set()
            for idx in table.selectedIndexes():
                item = table.item(idx.row(), 0)
                if item is None:
                    continue
                raw = item.data(Qt.ItemDataRole.UserRole)
                data_idx = raw if isinstance(raw, int) else idx.row()
                if data_idx in seen or not (0 <= data_idx < len(filtered)):
                    continue
                seen.add(data_idx)
                picked.append(filtered[data_idx])
            return picked

        def _on_sel() -> None:
            selected = _selected()
            if not selected:
                detail.setText("Выберите строку — здесь будет полное название и ID.")
                return
            if len(selected) == 1:
                app = selected[0]
                detail.setText(f"{app.display_name}\nStore ID: {app.store_id}")
                return
            lines = [f"Выбрано: {len(selected)}"]
            for app in selected[:12]:
                lines.append(f"• {app.display_name} — {app.store_id}")
            if len(selected) > 12:
                lines.append(f"… и ещё {len(selected) - 12}")
            detail.setText("\n".join(lines))

        table.itemSelectionChanged.connect(_on_sel)

        def on_use() -> None:
            selected = _selected()
            if not selected:
                QMessageBox.information(dialog, "Выбор", "Выберите приложение.")
                return
            app = selected[0]
            self.app_input.setText(app.store_id)
            dialog.accept()
            self.output.setPlainText(
                f"Из каталога: {app.display_name}\nID={app.store_id}"
            )

        def on_download() -> None:
            selected = _selected()
            if len(selected) != 1:
                QMessageBox.information(
                    dialog, "Скачать", "Для одной загрузки выберите ровно одну строку."
                )
                return
            app = selected[0]
            self.app_input.setText(app.store_id)
            dialog.accept()
            self._start_download(AppReference(store_id=app.store_id), confirm=True)

        def on_bulk() -> None:
            if not self._require_tos():
                return
            selected = _selected()
            if not selected:
                QMessageBox.information(
                    dialog, "Массовая загрузка", "Выберите одно или несколько приложений."
                )
                return
            ids = [a.store_id for a in selected]
            names = ", ".join(a.display_name for a in selected[:5])
            more = f" (+ещё {len(selected) - 5})" if len(selected) > 5 else ""
            answer = QMessageBox.question(
                dialog,
                "Массовая загрузка",
                f"Скачать {len(ids)} IPA одной консолью?\n"
                f"{names}{more}\n\n"
                "Passphrase один раз. Без лицензии на ID — FAIL и переход к следующему.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            before = self._appstore.list_ipa_names(self._packages_dir)
            try:
                self._appstore.begin_interactive_bulk_download(
                    ids,
                    self._packages_dir,
                    try_purchase=self.try_purchase_check.isChecked(),
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(dialog, "Массовая загрузка", str(exc))
                return
            self._download_before_names = before
            dialog.accept()
            self.card_app.set_state("active", "Массовая загрузка…")
            self.output.setPlainText(
                f"Консоль bulk-download открыта ({len(ids)} ID).\n"
                "1) Passphrase\n"
                "2) Дождитесь DONE\n"
                "3) «Подхватить IPA» для последнего/нового пакета"
            )

        use_btn.clicked.connect(on_use)
        dl_btn.clicked.connect(on_download)
        bulk_btn.clicked.connect(on_bulk)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def _on_pickup_ipa(self) -> None:
        raw = self.app_input.text().strip()
        preferred = raw if raw.isdigit() else getattr(self, "_download_store_id", None)
        path = self._choose_ipa_path(preferred_store_id=preferred, interactive=True)
        if path is None:
            return
        self._begin_inspect_ipa(path)

    def _choose_ipa_path(
        self,
        *,
        preferred_store_id: str | None,
        interactive: bool = True,
    ) -> Path | None:
        entries = self._appstore.list_ipa_entries(self._packages_dir)
        if not entries:
            if interactive:
                QMessageBox.information(
                    self,
                    "IPA",
                    f"В {self._packages_dir} нет .ipa.\n"
                    "Сначала скачайте приложение или положите файл в packages.",
                )
            return None

        before = getattr(self, "_download_before_names", set())
        before_mtimes = getattr(self, "_download_before_mtimes", {})
        auto = self._appstore.find_ipa_path(
            self._packages_dir,
            before_names=before,
            before_mtimes=before_mtimes,
            preferred_store_id=preferred_store_id,
        )
        # Match по Store ID — без диалога (автоподхват).
        sid = (preferred_store_id or "").strip()
        if sid.isdigit():
            matched = [e for e in entries if e[0].name.startswith(f"{sid}_")]
            if matched:
                return max(matched, key=lambda e: e[2])[0]
        if not interactive:
            return auto
        if len(entries) == 1:
            return entries[0][0]

        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите IPA")
        dialog.setMinimumWidth(560)
        dialog.setStyleSheet(_dialog_qss(self._mode))
        layout = QVBoxLayout(dialog)
        hint = preferred_store_id or "новейший"
        layout.addWidget(
            QLabel(f"Файлы в packages (предпочтение: {hint}):")
        )
        table = QTableWidget(len(entries), 3, dialog)
        table.setHorizontalHeaderLabels(["Файл", "МБ", "Дата"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        preselect = 0
        for row, (path, size, mtime) in enumerate(entries):
            table.setItem(row, 0, QTableWidgetItem(path.name))
            table.setItem(row, 1, QTableWidgetItem(f"{size / (1024 * 1024):.1f}"))
            table.setItem(
                row,
                2,
                QTableWidgetItem(datetime.fromtimestamp(mtime).strftime("%d.%m %H:%M")),
            )
            if auto is not None and path == auto:
                preselect = row
        table.selectRow(preselect)
        layout.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        table.doubleClicked.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        row = table.currentRow()
        if row < 0 or row >= len(entries):
            return None
        return entries[row][0]

    def _begin_inspect_ipa(self, path: Path) -> None:
        self._set_busy(True, f"Читаю IPA… {path.name}")
        self.output.setPlainText(
            f"Подхватываю {path.name}\n"
            "Чтение архива и SHA-256 для больших файлов может занять минуту…"
        )
        worker = InspectPackageWorker(self._appstore, str(path))
        worker.signals.finished.connect(self._on_download_done)
        worker.signals.failed.connect(self._on_worker_failed)
        self._thread_pool.start(worker)

    def _on_install(self) -> None:
        if self._busy or self._package is None:
            return
        if not self._require_tos():
            return
        if not self._devices:
            QMessageBox.information(self, "Установка", "Сначала найдите устройство.")
            return
        device = self._devices[0]
        pkg = self._package
        meets = device_meets_minimum(device.os_version, pkg.minimum_os_version)
        min_line = f"min iOS IPA: {pkg.minimum_os_version or 'неизвестно'}\n"
        if meets is False:
            answer = QMessageBox.warning(
                self,
                "iOS слишком старая",
                "Устройство, похоже, не тянет минимальную iOS этого IPA.\n\n"
                f"Устройство: iOS {device.os_version or '?'}\n"
                f"IPA требует: {pkg.minimum_os_version}\n\n"
                "Всё равно попытаться установить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        elif meets is True:
            min_line += f"Проверка min iOS: OK (устройство {device.os_version})\n"
        else:
            min_line += "Проверка min iOS: не удалось сравнить версии\n"
        answer = QMessageBox.question(
            self,
            "Подтверждение установки",
            "Установить пакет на устройство?\n\n"
            f"Устройство: {device.display_name} ({device.device_id})\n"
            f"iOS: {device.os_version or '?'}\n"
            f"{min_line}"
            f"Пакет: {pkg.local_path}\n"
            f"Размер: {pkg.size_bytes} байт\n"
            f"bundle_id: {pkg.bundle_id or 'неизвестно'}\n"
            f"version: {pkg.version or 'неизвестно'}\n\n"
            "Операция может изменить существующую установку.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True, "Установка через ideviceinstaller…")
        worker = InstallAppWorker(self._installer, pkg, device)
        worker.signals.finished.connect(self._on_install_done)
        worker.signals.failed.connect(self._on_worker_failed)
        self._thread_pool.start(worker)

    @staticmethod
    def _parse_app_reference(raw: str) -> AppReference:
        if raw.isdigit():
            return AppReference(store_id=raw)
        return AppReference(bundle_id=raw)

    def _on_devices_found(self, devices: object) -> None:
        assert isinstance(devices, list)
        self._devices = devices
        if not devices:
            self.set_device_chip(False)
            self.output.setPlainText("Устройства не найдены.")
        else:
            lines = [f"Найдено устройств: {len(devices)}"]
            for device in devices:
                avail = (
                    "доступно" if device.available_for_operations else "нужно доверие"
                )
                lines.append(
                    f"- {device.display_name} | UDID={device.device_id} | "
                    f"iOS={device.os_version or '?'} | {avail}"
                )
            first = devices[0]
            self.set_device_chip(
                True,
                first.display_name,
                trust_ok=bool(first.available_for_operations),
            )
            self.output.setPlainText("\n".join(lines))
        self._set_busy(False)

    def _on_paired(self, device: object) -> None:
        assert isinstance(device, DeviceInfo)
        self._devices = [device]
        self.set_device_chip(
            True,
            device.display_name,
            trust_ok=True,
            trust_error="",
        )
        self.output.setPlainText(
            "Доверие OK.\n"
            f"{device.display_name} | {device.device_id} | iOS {device.os_version or '?'}"
        )
        self._set_busy(False)

    def _on_download_done(self, package: PackageInfo) -> None:
        self._package = package
        self.install_button.setEnabled(True)
        self.card_app.set_state("done", "IPA готов")
        if "C" in self.tiles:
            self.tiles["C"].set_done(True)
        name = Path(package.local_path).name
        mb = package.size_bytes / (1024 * 1024)
        store_id = getattr(self, "_download_store_id", None)
        if not store_id:
            stem = Path(package.local_path).stem
            store_id = stem.split("_", 1)[0] if stem[:1].isdigit() else None
        display = self._last_display_name or package.bundle_id or name
        self._history.record_download(
            ipa_path=str(Path(package.local_path).resolve()),
            store_id=store_id,
            bundle_id=package.bundle_id,
            display_name=display,
            version=package.version,
        )
        self._set_download_progress_ui(
            phase="ok",
            percent=100,
            title="IPA готов к установке",
            detail=f"{display} · {name} · {mb:.1f} МБ",
            label="Можно нажать «Установить на устройство»",
        )
        self.output.setPlainText(
            f"IPA готов: {display}\n"
            f"Файл: {package.local_path}\n"
            f"bundle_id: {package.bundle_id or '—'} · "
            f"version: {package.version or '—'} · "
            f"min iOS: {package.minimum_os_version or '—'}\n"
            "Можно устанавливать на iPhone / iPad."
        )
        self._set_busy(False)

    def _on_install_done(self, payload: object) -> None:
        assert isinstance(payload, dict)
        pkg = self._package
        device = self._devices[0] if self._devices else None
        app_name = (
            self._last_display_name
            or (pkg.bundle_id if pkg else None)
            or Path(str(payload.get("package") or "app")).stem
        )
        if pkg is not None:
            store_id = getattr(self, "_download_store_id", None)
            self._history.record_install(
                ipa_path=str(Path(pkg.local_path).resolve()),
                device_name=device.display_name if device else None,
                store_id=store_id,
                bundle_id=pkg.bundle_id,
                display_name=app_name,
                version=pkg.version,
            )
        self._set_busy(False)
        if "D" in self.tiles:
            self.tiles["D"].set_done(True)
        show_install_success_dialog(
            self,
            app_name=str(app_name),
            device_name=(device.display_name if device else str(payload.get("device_id") or "устройство")),
            version=pkg.version if pkg else None,
            dialog_qss=_dialog_qss(self._mode),
        )
        self.output.setPlainText(
            f"Установлено: {app_name}\n"
            f"Устройство: {payload.get('device_id')}\n"
            "Откройте приложение на iPhone / iPad."
        )

    def _on_device_worker_failed(self, message: str) -> None:
        name = ""
        trust_ok = False
        if self._devices:
            name = self._devices[0].display_name
            trust_ok = bool(self._devices[0].available_for_operations)
        lower = message.casefold()
        trust_err = None
        if any(
            key in lower
            for key in (
                "trust",
                "pair",
                "довер",
                "сопряж",
                "password protected",
                "lockdownd",
            )
        ):
            trust_err = message.strip().splitlines()[0][:160]
            trust_ok = False
        self.set_device_chip(
            self._device_ok and bool(self._devices),
            name,
            trust_ok=trust_ok if self._devices else False,
            trust_error=trust_err if trust_err is not None else None,
        )
        self._on_worker_failed(message)

    def _on_worker_failed(self, message: str) -> None:
        self._set_busy(False)
        if "PURCHASES_FETCH_FAILED" in message:
            QMessageBox.information(
                self,
                "Архив покупок",
                "Нужно войти в Apple ID.\n"
                "Справа вверху нажмите «Apple ID…» → «Войти» "
                "и введите логин, пароль и код из SMS в чёрном окне.",
            )
            return
        if "SEARCH_FAILED" in message or "keyring" in message.lower():
            QMessageBox.information(
                self,
                "Поиск",
                "Нужно войти в Apple ID.\n"
                "Справа вверху: «Apple ID…» → «Войти».\n"
                "Или ищите через «Найти ID…» без входа — это только поиск номера.",
            )
            return
        self.output.setPlainText(message)

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self._busy = busy
        self.progress.set_busy(busy)
        session_ok = self._appstore.session_files_present()
        for btn in (
            self.btn_find,
            self.btn_trust,
            self.btn_login,
            self.btn_check,
            self.btn_logout,
            self.btn_save_pass,
            self.btn_clear_pass,
            self.download_button,
            self.pickup_button,
            self.history_button,
            self.versions_button,
            self.pickup_versions_button,
            self.catalog_button,
            self.install_button,
            self.archive_button,
            self.pickup_archive_button,
            self.regional_search_button,
            *self._region_tags.values(),
            self.diag_button,
            self.help_button,
            self.release_notes_button,
            self.open_setup_button,
            self.doctor_button,
            self.replay_onboarding_button,
            self.shortcut_button,
            self.theme_toggle,
        ):
            if btn is self.install_button:
                btn.setEnabled((not busy) and self._package is not None)
            elif btn in (
                self.archive_button,
                self.pickup_archive_button,
                self.versions_button,
            ):
                btn.setEnabled((not busy) and session_ok)
            else:
                btn.setEnabled(not busy)
        if status:
            self.output.setPlainText(status)
