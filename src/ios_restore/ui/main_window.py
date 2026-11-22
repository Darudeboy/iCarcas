"""Main window: device detection, App Store via interactive ipatool console, install."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
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
from ios_restore.infrastructure.paths import default_tools_dir
from ios_restore.ui.brand_icon import StackingLogoWidget, icon_png_path, load_app_icon
from ios_restore.ui.history_dialog import show_history_dialog, show_install_success_dialog
from ios_restore.ui.onboarding import (
    ensure_onboarding,
    show_help_dialog,
    show_setup_dialog,
)
from ios_restore.ui.release_notes import show_release_notes_dialog
from ios_restore.ui.theme import PALETTES, build_stylesheet, repolish
from ios_restore.ui.tos import ensure_tos_accepted, tos_accepted
from ios_restore.ui.workers import (
    AuthInfoWorker,
    DetectDevicesWorker,
    InspectPackageWorker,
    InstallAppWorker,
    PairDeviceWorker,
    RegionalSearchAppWorker,
)

_DIALOG_QSS = (
    "* { background-color: #ffffff; color: #000000; }"
    "QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #cccccc; }"
    "QTableWidget::item { background-color: #ffffff; color: #000000; padding: 4px; }"
    "QTableWidget::item:selected { background-color: #0078d7; color: #ffffff; }"
    "QHeaderView::section { background-color: #f0f0f0; color: #000000;"
    " border: 1px solid #cccccc; padding: 4px; }"
    "QPushButton { background-color: #e0e0e0; color: #000000;"
    " border: 1px solid #999999; padding: 6px 12px; }"
    "QPushButton:hover { background-color: #d0d0d0; }"
    "QCheckBox { color: #000000; }"
    "QLabel { color: #000000; }"
    "QLabel#selectionDetail { background-color: #f7f7f7; border: 1px solid #cccccc;"
    " padding: 8px; }"
)

_EMPTY_CELL = "—"


def _light_dialog_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#000000"))
    return pal


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
        item.setForeground(QColor("#000000"))
        item.setBackground(QColor("#ffffff"))
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
) -> None:
    """Full text visible: no elide, resize-to-contents, hide all-empty columns."""
    table.setWordWrap(True)
    table.setTextElideMode(Qt.TextElideMode.ElideNone)
    table.setAlternatingRowColors(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setSortingEnabled(True)
    table.verticalHeader().setVisible(True)
    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    for col in range(table.columnCount()):
        if hide_empty_columns and _column_is_empty(table, col):
            table.setColumnHidden(col, True)
            continue
        table.setColumnHidden(col, False)
        if col == name_col:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    table.resizeRowsToContents()
    # After stretch, ensure name still readable: min width.
    if 0 <= name_col < table.columnCount() and not table.isColumnHidden(name_col):
        table.setColumnWidth(name_col, max(table.columnWidth(name_col), 280))


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
        outer.setContentsMargins(20, 18, 20, 20)
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
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("chip")
        self.setProperty("state", "idle")

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
        # Wider default: region chips + 3-button rows need room; 640 clipped the right edge.
        self.resize(880, 780)
        self.setMinimumSize(760, 560)

        self._thread_pool = QThreadPool.globalInstance()
        self._packages_dir = packages_dir or (Path.cwd() / "packages")
        self._busy = False
        self._devices: list[DeviceInfo] = []
        self._package: PackageInfo | None = None
        self._mode = mode if mode in PALETTES else "dark"
        tools = default_tools_dir()
        self._device_adapter = DeviceCliAdapter(tools_dir=tools)
        self._appstore = AppStoreCliAdapter(tools_dir=tools)
        self._installer = InstallCliAdapter(tools_dir=tools)
        # Умный поиск: локальный каталог ID + iTunes (ранжирование, без мусора).
        self._smart_search = SmartAppSearchService()
        self._license_check = LicenseCheckService()
        self._history = HistoryStore(self._packages_dir / "icarcas-history.json")
        self._purchases_dump_path = self._appstore.purchases_dump_path(self._packages_dir)
        self._purchases_cache: list[PurchasedApp] | None = None
        self._account_storefront: str | None = None
        self._last_display_name: str | None = None
        # Defer ToS/onboarding until the window is actually shown so BrandSplash
        # can finish its layer animation on first run (singleShot(0) stole the
        # event loop with a modal dialog while the splash was still up).
        self._bootstrap_scheduled = False

        shell = QWidget()
        shell.setObjectName("root")
        self.setCentralWidget(shell)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("mainScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Keep content within the viewport — horizontal scroll made the right edge look "eaten".
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        shell_layout.addWidget(scroll)

        central = QWidget()
        central.setObjectName("root")
        central.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        scroll.setWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(16)

        header = QHBoxLayout()
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        self.brand_mark = StackingLogoWidget(self, size=44)
        self.brand_mark.set_progress(1.0)
        brand_row.addWidget(self.brand_mark, 0, Qt.AlignmentFlag.AlignVCenter)
        # Transparent PNG mark (no black plate) — works on light and dark.
        self.brand_raster = QLabel()
        self.brand_raster.setFixedSize(44, 44)
        brand_row.addWidget(self.brand_raster, 0, Qt.AlignmentFlag.AlignVCenter)
        self._refresh_brand_mark()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setObjectName("appTitle")
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        self._refresh_title()
        sub = QLabel("Восстановление своих приложений на iOS (iPhone / iPad)")
        sub.setObjectName("appSubtitle")
        sub.setWordWrap(True)
        titles.addWidget(self.title_label)
        titles.addWidget(sub)
        brand_row.addLayout(titles, 1)
        header.addLayout(brand_row, 1)

        corner_row = QHBoxLayout()
        corner_row.setSpacing(8)
        self.device_button = make_corner_button("iOS…")
        self.device_button.setToolTip("Найти iPhone / iPad или возобновить подключение")
        self._rebuild_device_menu()
        self.session_button = make_corner_button("Войти…")
        self.session_button.setToolTip("Сессия App Store: войти или возобновить")
        self._device_ok = False
        self._session_ok = False
        self._session_label: str | None = None
        self._rebuild_session_menu()
        corner_row.addWidget(self.device_button)
        corner_row.addWidget(self.session_button)
        header.addLayout(corner_row)
        root.addLayout(header)

        # Full-width nav — do not pack under iOS/session chips (that ate the right edge).
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.open_setup_button = make_button("Впервые здесь?", "header")
        self.open_setup_button.setProperty("emphasis", "1")
        repolish(self.open_setup_button)
        self.open_setup_button.setToolTip(
            "Первая установка: что поставить, чтобы увидеть iPhone/iPad"
        )
        self.open_setup_button.clicked.connect(lambda: show_setup_dialog(self))
        self.release_notes_button = make_button("Что нового", "header")
        self.release_notes_button.setToolTip("Изменения с последнего релиза")
        self.release_notes_button.clicked.connect(lambda: show_release_notes_dialog(self))
        self.help_button = make_button("Справка", "header")
        self.help_button.setToolTip("Как пользоваться — кратко по шагам")
        self.help_button.clicked.connect(lambda: show_help_dialog(self))
        self.replay_onboarding_button = make_button("Обучение", "header")
        self.replay_onboarding_button.setToolTip("Повторить знакомство при старте")
        self.replay_onboarding_button.clicked.connect(self._on_replay_onboarding)
        self.theme_button = make_button("", "header")
        self.theme_button.setToolTip("Переключить светлую / тёмную тему")
        self.theme_button.clicked.connect(self._toggle_theme)
        self._refresh_theme_button()
        # Aliases: old help-card buttons removed (they duplicated this nav row).
        self.open_help_button = self.help_button
        self.open_release_notes_button = self.release_notes_button
        for btn in (
            self.open_setup_button,
            self.release_notes_button,
            self.help_button,
            self.replay_onboarding_button,
            self.theme_button,
        ):
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            nav_row.addWidget(btn)
        nav_row.addStretch(1)
        root.addLayout(nav_row)

        self.privacy_label = QLabel(
            "Учётные данные и ключ сессии хранятся только на этом компьютере "
            "и никуда не передаются."
        )
        self.privacy_label.setObjectName("privacyNotice")
        self.privacy_label.setWordWrap(True)
        root.addWidget(self.privacy_label)

        # Kept as aliases for older call sites / busy toggles (hidden, menu-driven).
        self.detect_button = self.device_button
        self.pair_button = self.device_button
        self.login_button = self.session_button
        self.auth_info_button = self.session_button
        self.logout_button = self.session_button
        self.remember_pass_button = self.session_button
        self.clear_pass_button = self.session_button
        self.chip_device = Chip("")
        self.chip_session = Chip("")
        self.chip_device.hide()
        self.chip_session.hide()
        self.passphrase_chip = QLabel()
        self.passphrase_chip.hide()
        self._refresh_passphrase_label()

        self.card_store = Card("Поиск", step=1)
        archive_row = QHBoxLayout()
        archive_row.setSpacing(10)
        self.archive_button = make_button("Архив покупок…")
        self.archive_button.setToolTip("Список приложений с лицензией на этом Apple ID")
        self.archive_button.clicked.connect(self._on_archive_purchases)
        self.pickup_archive_button = make_button("Подхватить архив")
        self.pickup_archive_button.setToolTip("Показать результат после дампа покупок")
        self.pickup_archive_button.clicked.connect(self._on_pickup_purchases_dump)
        archive_row.addWidget(self.archive_button, 1)
        archive_row.addWidget(self.pickup_archive_button, 1)
        self.card_store.body.addLayout(archive_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Название, Store ID или bundle…")
        self.search_input.setClearButtonEnabled(True)
        self._region_code = "RU"
        self._region_tags: dict[str, QPushButton] = {}
        region_grid = QGridLayout()
        region_grid.setHorizontalSpacing(6)
        region_grid.setVerticalSpacing(6)
        region_cols = 4
        for index, region in enumerate(RegionalAppSearchService.known_regions()):
            tag = QPushButton(region.name)
            tag.setObjectName("regionTag")
            tag.setCursor(Qt.CursorShape.PointingHandCursor)
            tag.setCheckable(False)
            tag.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            tag.setToolTip(f"Регион App Store: {region.name} ({region.code})")
            tag.clicked.connect(
                lambda _checked=False, code=region.code: self._select_region(code)
            )
            self._region_tags[region.code] = tag
            region_grid.addWidget(tag, index // region_cols, index % region_cols)
        self._select_region("RU")
        self.regional_search_button = make_button("Найти ID…", "primary")
        self.regional_search_button.clicked.connect(self._on_regional_search_app)
        self.regional_search_button.setToolTip(
            "Найти Store ID. Скачивание — только при лицензии на аккаунте."
        )
        self.card_store.body.addWidget(self.search_input)
        self.card_store.body.addLayout(region_grid)
        self.card_store.body.addWidget(self.regional_search_button)
        self.card_store.set_state("active")
        root.addWidget(self.card_store)
        repolish(self.regional_search_button)

        self.card_app = Card("Приложение", step=2)
        self.app_input = QLineEdit()
        self.app_input.setPlaceholderText(
            "Bundle id (com.example.app) или App Store ID"
        )
        self.app_input.setClearButtonEnabled(True)
        self.card_app.body.addWidget(self.app_input)
        self.try_purchase_check = QCheckBox(
            "Попробовать оформить лицензию в текущем регионе"
        )
        self.try_purchase_check.setToolTip(
            "Только если приложение доступно на витрине текущего Apple ID. "
            "Чужой регион не открывает."
        )
        self.card_app.body.addWidget(self.try_purchase_check)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.download_button = make_button("Скачать IPA…")
        self.download_button.clicked.connect(self._on_download)
        self.pickup_button = make_button("Подхватить IPA")
        self.pickup_button.clicked.connect(self._on_pickup_ipa)
        self.history_button = make_button("История…")
        self.history_button.setToolTip("Последние скачивания и установки")
        self.history_button.clicked.connect(self._on_open_history)
        row.addWidget(self.download_button, 1)
        row.addWidget(self.pickup_button, 1)
        row.addWidget(self.history_button, 1)
        self.card_app.body.addLayout(row)
        versions_row = QHBoxLayout()
        versions_row.setSpacing(10)
        self.versions_button = make_button("Версии…")
        self.versions_button.setToolTip(
            "list-versions: дамп доступных версий для числового Store ID "
            "(нужна сессия; затем «Подхватить версии»)"
        )
        self.versions_button.clicked.connect(self._on_list_versions)
        self.pickup_versions_button = make_button("Подхватить версии")
        self.pickup_versions_button.clicked.connect(self._on_pickup_versions)
        self.catalog_button = make_button("Каталог ID…")
        self.catalog_button.setToolTip(
            "Локальный список Store ID (как AppsList у IPA_Downloader). "
            "Мультивыбор → массовая загрузка."
        )
        self.catalog_button.clicked.connect(self._on_open_catalog)
        versions_row.addWidget(self.versions_button, 1)
        versions_row.addWidget(self.pickup_versions_button, 1)
        versions_row.addWidget(self.catalog_button, 1)
        self.card_app.body.addLayout(versions_row)
        self.download_status_panel = QFrame()
        self.download_status_panel.setObjectName("downloadStatusPanel")
        self.download_status_panel.setProperty("phase", "idle")
        dl_status_layout = QVBoxLayout(self.download_status_panel)
        dl_status_layout.setContentsMargins(12, 10, 12, 10)
        dl_status_layout.setSpacing(6)
        self.download_state_title = QLabel("Загрузка не запущена")
        self.download_state_title.setObjectName("downloadStateTitle")
        self.download_state_title.setProperty("phase", "idle")
        dl_status_layout.addWidget(self.download_state_title)
        self.download_state_detail = QLabel(
            "После «Скачать IPA…» здесь будет видно: идёт ли закачка, сколько МБ и сколько времени прошло."
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
        self.card_app.body.addWidget(self.download_status_panel)
        dl_ctrl = QHBoxLayout()
        dl_ctrl.setSpacing(10)
        self.cancel_download_button = make_button("Отменить загрузку", "danger")
        self.cancel_download_button.setEnabled(False)
        self.cancel_download_button.clicked.connect(self._on_cancel_download)
        self.diag_button = make_button("Диагностика…", "ghost")
        self.diag_button.clicked.connect(self._on_export_diagnostics)
        dl_ctrl.addWidget(self.cancel_download_button, 1)
        dl_ctrl.addWidget(self.diag_button, 1)
        self.card_app.body.addLayout(dl_ctrl)
        self.install_button = make_button("Установить на устройство", "primary")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._on_install)
        self.card_app.body.addWidget(self.install_button)
        root.addWidget(self.card_app)
        self._versions_dump_path: Path | None = None
        self._catalog_cache: list[CatalogApp] | None = None
        self._download_poll: QTimer | None = None
        self._download_started_at: float | None = None
        self._download_last_bytes: int = 0
        self._download_last_bytes_at: float | None = None
        self._download_peak_bytes: int = 0

        log_card = Card("Журнал")
        self.btn_clear_log = make_button("Очистить", "ghost")
        head_layout = log_card.layout().itemAt(0).layout()
        assert isinstance(head_layout, QHBoxLayout)
        head_layout.insertWidget(2, self.btn_clear_log)
        self.output = QPlainTextEdit()
        self.output.setObjectName("log")
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(140)
        log_card.body.addWidget(self.output)
        self.btn_clear_log.clicked.connect(self.output.clear)
        root.addWidget(log_card, 1)

        self._append_env_status()
        session_ok = self._appstore.session_files_present()
        self.set_session_chip(session_ok)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._bootstrap_scheduled:
            return
        self._bootstrap_scheduled = True
        QTimer.singleShot(0, self._bootstrap_tos_and_session)

    def _refresh_title(self) -> None:
        accent = PALETTES[self._mode]["accent"]
        self.title_label.setText(f'<span style="color:{accent}">i</span>Carcas')

    def _refresh_brand_mark(self) -> None:
        """Header mark: transparent raster if present, else procedural stack."""
        from PySide6.QtGui import QPixmap

        png = icon_png_path(transparent=True)
        if png.is_file():
            pix = QPixmap(str(png)).scaled(
                44,
                44,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.brand_raster.setPixmap(pix)
            self.brand_raster.show()
            self.brand_mark.hide()
            return
        self.brand_raster.hide()
        self.brand_mark.set_progress(1.0)
        self.brand_mark.show()

    def _refresh_theme_button(self) -> None:
        # Short label — long "Тёмная тема" was clipped in the header.
        if self._mode == "dark":
            self.theme_button.setText("Светлая")
        else:
            self.theme_button.setText("Тёмная")

    def _toggle_theme(self) -> None:
        self.apply_theme("light" if self._mode == "dark" else "dark")

    def apply_theme(self, mode: str) -> None:
        if mode not in PALETTES:
            mode = "dark"
        self._mode = mode
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(mode))
        self._refresh_title()
        self._refresh_theme_button()
        self._refresh_brand_mark()
        # Dynamic properties (chips / badges) need a polish pass after QSS swap.
        for widget in self.findChildren(QWidget):
            if widget.property("state") is not None or widget.property("variant") is not None:
                repolish(widget)
        QSettings("iCarcas", "iCarcas").setValue("theme", mode)

    def log(self, text: str) -> None:
        self.output.appendPlainText(text)

    def _rebuild_device_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Найти устройство", self._on_detect)
        menu.addAction("Установить доверие", self._on_pair)
        self.device_button.setMenu(menu)

    def _rebuild_session_menu(self) -> None:
        menu = QMenu(self)
        if self._session_ok:
            menu.addAction("Проверить сессию…", self._on_auth_info)
            menu.addAction("Возобновить вход…", self._on_login)
            menu.addSeparator()
            menu.addAction("Запомнить ключ…", self._on_save_passphrase)
            menu.addAction("Забыть ключ", self._on_clear_passphrase)
            menu.addSeparator()
            menu.addAction("Выйти…", self._on_logout)
        else:
            menu.addAction("Войти…", self._on_login)
            menu.addAction("Проверить сессию…", self._on_auth_info)
            menu.addSeparator()
            menu.addAction("Запомнить ключ…", self._on_save_passphrase)
            menu.addAction("Забыть ключ", self._on_clear_passphrase)
        self.session_button.setMenu(menu)

    def _paint_device_corner(self, *, state: str, text: str) -> None:
        self.device_button.setText(text)
        self.device_button.setProperty("state", state)
        repolish(self.device_button)

    def set_device_working(self, text: str) -> None:
        """Green highlight while detecting / pairing."""
        self._paint_device_corner(state="busy", text=text)

    def set_device_chip(self, found: bool, name: str = "") -> None:
        self._device_ok = found
        if found and name:
            label = name if len(name) <= 22 else name[:20] + "…"
        elif found:
            label = "iOS OK"
        else:
            label = "iOS…"
        self._paint_device_corner(state="ok" if found else "idle", text=label)
        self.chip_device.set_state(found, label)
        if found:
            self.card_store.set_state("active")

    def set_session_chip(self, ok: bool, detail: str | None = None) -> None:
        if detail:
            self._session_label = detail
        if not ok:
            self._session_label = None
        self._session_ok = ok
        if ok:
            label = self._session_label or "Сессия OK"
            if len(label) > 24:
                label = label[:22] + "…"
        else:
            label = "Войти…"
        self.session_button.setText(label)
        self.session_button.setProperty("state", "ok" if ok else "idle")
        repolish(self.session_button)
        self.chip_session.set_state(ok, label)
        self._rebuild_session_menu()
        self._refresh_passphrase_label()
        self.card_store.set_state(
            "done" if ok else "active",
            "Готово" if ok else "",
        )
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
                "Откройте «Справка» или «Повторить обучение».",
            )
        self._refresh_passphrase_label()
        if self._appstore.session_files_present() and kc_pass.has_stored_passphrase():
            worker = AuthInfoWorker(self._appstore)
            worker.signals.finished.connect(self._on_auth_info_done)
            worker.signals.failed.connect(lambda _m: None)
            self._thread_pool.start(worker)

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
            base = self.session_button.toolTip().split("\n")[0]
            if not base:
                base = "Сессия App Store"
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
        detail = "Сессия OK"
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
        try:
            tools = EnvironmentCliAdapter().check_tools()
            session = (
                "локальные файлы сессии ipatool есть"
                if self._appstore.session_files_present()
                else "файлы сессии ipatool не найдены — нужен login"
            )
            self.output.setPlainText(
                "CLI готовы: "
                + ", ".join(tools)
                + f"\nКаталог tools: {default_tools_dir()}"
                + f"\nПакеты: {self._packages_dir}"
                + f"\nСессия: {session}"
                + "\n\nЕсли GUI писал ошибку keyring — это ограничение Windows/ipatool. "
                "Используйте кнопки с «…»: passphrase вводится в консоли."
            )
        except Exception as exc:  # noqa: BLE001
            self.output.setPlainText(f"Проверка окружения: {exc}")

    def _on_detect(self) -> None:
        if self._busy:
            return
        self.set_device_working("Поиск…")
        self._set_busy(True, "Поиск устройств…")
        worker = DetectDevicesWorker(self._device_adapter)
        worker.signals.finished.connect(self._on_devices_found)
        worker.signals.failed.connect(self._on_device_worker_failed)
        self._thread_pool.start(worker)

    def _on_pair(self) -> None:
        if self._busy:
            return
        if not self._devices:
            QMessageBox.information(self, "Нет устройства", "Сначала найдите устройство.")
            return
        device = self._devices[0]
        QMessageBox.information(
            self,
            "Доверие",
            "Разблокируйте устройство и при запросе нажмите «Доверять».",
        )
        self.set_device_working("Связь…")
        self._set_busy(True, f"Установка доверия для {device.device_id}…")
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
            dialog_qss=_DIALOG_QSS,
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
        dialog.setStyleSheet(_DIALOG_QSS)
        pal = _light_dialog_palette()
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
        dialog.setStyleSheet(_DIALOG_QSS)
        pal = _light_dialog_palette()
        dialog.setPalette(pal)

        layout = QVBoxLayout(dialog)
        hint = QLabel(
            f"Каталог + iTunes ({region_code}). "
            "Карточка ниже: регион и оценка лицензии до скачивания."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        table = QTableWidget(len(results), 7, dialog)
        table.setPalette(pal)
        table.setAutoFillBackground(True)
        table.setHorizontalHeaderLabels(
            ["Название", "Store ID", "Источник", "Bundle ID", "Версия", "Цена", "Seller"]
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
                    app.seller_name or "",
                ),
                data_index=row_idx,
            )
        _tune_data_table(table, name_col=0, hide_empty_columns=True)
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
            if data_idx is None or not (0 <= data_idx < len(results)):
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
                f"Версия: {app.version or '—'}"
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
        dialog.setStyleSheet(_DIALOG_QSS)
        pal = _light_dialog_palette()
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
        dialog.setStyleSheet(_DIALOG_QSS)
        pal = _light_dialog_palette()
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
        dialog.setStyleSheet(_DIALOG_QSS)
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
            self.set_device_chip(True, devices[0].display_name)
            self.output.setPlainText("\n".join(lines))
        self._set_busy(False)

    def _on_paired(self, device: object) -> None:
        assert isinstance(device, DeviceInfo)
        self._devices = [device]
        self.set_device_chip(True, device.display_name)
        self.output.setPlainText(
            "Доверие OK.\n"
            f"{device.display_name} | {device.device_id} | iOS {device.os_version or '?'}"
        )
        self._set_busy(False)

    def _on_download_done(self, package: PackageInfo) -> None:
        self._package = package
        self.install_button.setEnabled(True)
        self.card_app.set_state("done", "IPA готов")
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
        show_install_success_dialog(
            self,
            app_name=str(app_name),
            device_name=(device.display_name if device else str(payload.get("device_id") or "устройство")),
            version=pkg.version if pkg else None,
            dialog_qss=_DIALOG_QSS,
        )
        self.output.setPlainText(
            f"Установлено: {app_name}\n"
            f"Устройство: {payload.get('device_id')}\n"
            "Откройте приложение на iPhone / iPad."
        )

    def _on_device_worker_failed(self, message: str) -> None:
        name = ""
        if self._devices:
            name = self._devices[0].display_name
        self.set_device_chip(self._device_ok and bool(self._devices), name)
        self._on_worker_failed(message)

    def _on_worker_failed(self, message: str) -> None:
        self._set_busy(False)
        if "PURCHASES_FETCH_FAILED" in message:
            QMessageBox.information(
                self,
                "Архив покупок",
                "Сессия App Store не найдена или истекла.\n"
                "Сначала нажмите «Войти…» и завершите авторизацию "
                "в консоли ipatool (Apple ID, пароль, Keychain passphrase, 2FA).",
            )
            return
        if "SEARCH_FAILED" in message or "keyring" in message.lower():
            QMessageBox.information(
                self,
                "Поиск в App Store",
                "Поиск через ipatool требует активной сессии App Store.\n"
                "Сначала нажмите «Войти…» и завершите авторизацию.\n"
                "Или используйте «Найти по регионам…» — поиск без входа в аккаунт.",
            )
            return
        self.output.setPlainText(message)

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self._busy = busy
        session_ok = self._appstore.session_files_present()
        for btn in (
            self.device_button,
            self.session_button,
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
            self.open_help_button,
            self.open_release_notes_button,
            self.replay_onboarding_button,
        ):
            if btn is self.install_button:
                btn.setEnabled((not busy) and self._package is not None)
            elif btn in (self.archive_button, self.pickup_archive_button, self.versions_button):
                btn.setEnabled((not busy) and session_ok)
            else:
                btn.setEnabled(not busy)
        if status:
            self.output.setPlainText(status)
