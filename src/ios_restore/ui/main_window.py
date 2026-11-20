"""Main window: device detection, App Store via interactive ipatool console, install."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ios_restore.application.regional_search_service import RegionalAppSearchService
from ios_restore.application.smart_search_service import SmartAppSearchService
from ios_restore.domain.models import (
    AppReference,
    AppSearchResult,
    AppVersionInfo,
    CatalogApp,
    DeviceInfo,
    PackageInfo,
    PurchasedApp,
)
from ios_restore.domain.version_compare import device_meets_minimum
from ios_restore.infrastructure.apps_catalog import filter_catalog, load_apps_catalog
from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter
from ios_restore.infrastructure.device_cli_adapter import DeviceCliAdapter
from ios_restore.infrastructure.environment_cli_adapter import EnvironmentCliAdapter
from ios_restore.infrastructure.install_cli_adapter import InstallCliAdapter
from ios_restore.infrastructure.paths import default_tools_dir
from ios_restore.ui.theme import PALETTES, build_stylesheet, repolish
from ios_restore.ui.workers import (
    DetectDevicesWorker,
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
    item = table.item(row_idx, 0)
    if item is None:
        return None
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


class MainWindow(QMainWindow):
    def __init__(
        self,
        packages_dir: Path | None = None,
        *,
        mode: str = "dark",
    ) -> None:
        super().__init__()
        self.setWindowTitle("iCarcas")
        self.resize(640, 720)
        self.setMinimumSize(520, 480)

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
        self._purchases_dump_path = self._appstore.purchases_dump_path(self._packages_dir)

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
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setObjectName("appTitle")
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        self._refresh_title()
        sub = QLabel("Восстановление своих приложений на iPhone")
        sub.setObjectName("appSubtitle")
        titles.addWidget(self.title_label)
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(6)
        theme_row = QHBoxLayout()
        theme_row.setSpacing(0)
        theme_row.addStretch(1)
        self.theme_button = make_button("", "ghost")
        self.theme_button.setToolTip("Переключить светлую / тёмную тему")
        self.theme_button.clicked.connect(self._toggle_theme)
        self._refresh_theme_button()
        theme_row.addWidget(self.theme_button)
        right.addLayout(theme_row)
        self.chip_device = Chip("iPhone не найден")
        self.chip_session = Chip("Нет сессии App Store")
        right.addWidget(self.chip_device, 0, Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.chip_session, 0, Qt.AlignmentFlag.AlignRight)
        header.addLayout(right)
        root.addLayout(header)

        self.card_device = Card("Устройство", step=1)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.detect_button = make_button("Найти устройство")
        self.detect_button.clicked.connect(self._on_detect)
        self.pair_button = make_button("Установить доверие")
        self.pair_button.clicked.connect(self._on_pair)
        row.addWidget(self.detect_button, 1)
        row.addWidget(self.pair_button, 1)
        self.card_device.body.addLayout(row)
        self.card_device.set_state("active")
        root.addWidget(self.card_device)

        self.card_store = Card(
            "App Store",
            step=2,
            hint=(
                "Пароль, 2FA и Keychain passphrase вводятся в консоли ipatool — "
                "она откроется сама."
            ),
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        self.login_button = make_button("Войти…")
        self.login_button.clicked.connect(self._on_login)
        self.login_button.setToolTip(
            "Войти в App Store (нужен для архива покупок и download IPA)"
        )
        self.auth_info_button = make_button("Проверить сессию…")
        self.auth_info_button.clicked.connect(self._on_auth_info)
        self.logout_button = make_button("Выйти…", "danger")
        self.logout_button.clicked.connect(self._on_logout)
        row.addWidget(self.login_button, 1)
        row.addWidget(self.auth_info_button, 1)
        row.addWidget(self.logout_button, 1)
        self.card_store.body.addLayout(row)

        archive_row = QHBoxLayout()
        archive_row.setSpacing(10)
        self.archive_button = make_button("Архив покупок…")
        self.archive_button.setToolTip(
            "Открывает консоль: passphrase → полный дамп покупок текущего Apple ID"
        )
        self.archive_button.clicked.connect(self._on_archive_purchases)
        self.pickup_archive_button = make_button("Подхватить архив")
        self.pickup_archive_button.setToolTip(
            f"Читает {self._purchases_dump_path.name} после завершения дампа"
        )
        self.pickup_archive_button.clicked.connect(self._on_pickup_purchases_dump)
        archive_row.addWidget(self.archive_button, 1)
        archive_row.addWidget(self.pickup_archive_button, 1)
        self.card_store.body.addLayout(archive_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Название, Store ID или bundle… (каталог + iTunes)"
        )
        self.search_input.setClearButtonEnabled(True)
        self.region_combo = QComboBox()
        self.region_combo.setObjectName("regionCombo")
        for region in RegionalAppSearchService.known_regions():
            self.region_combo.addItem(f"{region.name} ({region.code})", region.code)
        ru_index = self.region_combo.findData("RU")
        if ru_index >= 0:
            self.region_combo.setCurrentIndex(ru_index)
        self.regional_search_button = make_button("Найти ID…", "primary")
        self.regional_search_button.clicked.connect(self._on_regional_search_app)
        self.regional_search_button.setToolTip(
            "Сначала локальный каталог (в т.ч. delisted), затем iTunes Lookup/Search "
            "с отсечением нерелевантных результатов. "
            "Скачивание — только при лицензии на текущем Apple ID."
        )
        self.card_store.body.addWidget(self.search_input)
        self.card_store.body.addWidget(self.region_combo)
        self.card_store.body.addWidget(self.regional_search_button)
        root.addWidget(self.card_store)
        repolish(self.regional_search_button)

        self.card_app = Card("Приложение", step=3)
        self.app_input = QLineEdit()
        self.app_input.setPlaceholderText(
            "Bundle id (com.example.app) или App Store ID"
        )
        self.app_input.setClearButtonEnabled(True)
        self.card_app.body.addWidget(self.app_input)
        self.try_purchase_check = QCheckBox(
            "Попробовать получить лицензию в текущем регионе (--purchase)"
        )
        self.try_purchase_check.setToolTip(
            "Не обходит чужой регион: лицензия оформляется только если приложение "
            "доступно на витрине текущего Apple ID (часто бесплатное)."
        )
        self.card_app.body.addWidget(self.try_purchase_check)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.download_button = make_button("Скачать IPA…")
        self.download_button.clicked.connect(self._on_download)
        self.pickup_button = make_button("Подхватить IPA")
        self.pickup_button.clicked.connect(self._on_pickup_ipa)
        row.addWidget(self.download_button, 1)
        row.addWidget(self.pickup_button, 1)
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
        self.install_button = make_button("Установить на iPhone", "primary")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._on_install)
        self.card_app.body.addWidget(self.install_button)
        root.addWidget(self.card_app)
        self._versions_dump_path: Path | None = None
        self._catalog_cache: list[CatalogApp] | None = None

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

    def _refresh_title(self) -> None:
        accent = PALETTES[self._mode]["accent"]
        self.title_label.setText(f'<span style="color:{accent}">i</span>Carcas')

    def _refresh_theme_button(self) -> None:
        if self._mode == "dark":
            self.theme_button.setText("Светлая тема")
        else:
            self.theme_button.setText("Тёмная тема")

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
        # Dynamic properties (chips / badges) need a polish pass after QSS swap.
        for widget in self.findChildren(QWidget):
            if widget.property("state") is not None or widget.property("variant") is not None:
                repolish(widget)
        QSettings("iCarcas", "iCarcas").setValue("theme", mode)

    def log(self, text: str) -> None:
        self.output.appendPlainText(text)

    def set_device_chip(self, found: bool, name: str = "") -> None:
        self.chip_device.set_state(
            found,
            name or ("iPhone подключён" if found else "iPhone не найден"),
        )
        self.card_device.set_state(
            "done" if found else "active",
            "Готово" if found else "",
        )
        if found:
            self.card_store.set_state("active")

    def set_session_chip(self, ok: bool) -> None:
        self.chip_session.set_state(
            ok,
            "Сессия App Store активна" if ok else "Нет сессии App Store",
        )
        self.card_store.set_state(
            "done" if ok else "active",
            "Готово" if ok else "",
        )
        if ok:
            self.card_app.set_state("active")
        self.archive_button.setEnabled(ok)
        self.pickup_archive_button.setEnabled(ok)

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
        self._set_busy(True, "Поиск устройств…")
        worker = DetectDevicesWorker(self._device_adapter)
        worker.signals.finished.connect(self._on_devices_found)
        worker.signals.failed.connect(self._on_worker_failed)
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
            "Разблокируйте iPhone и при запросе нажмите «Доверять».",
        )
        self._set_busy(True, f"Установка доверия для {device.device_id}…")
        worker = PairDeviceWorker(self._device_adapter, device.device_id)
        worker.signals.finished.connect(self._on_paired)
        worker.signals.failed.connect(self._on_worker_failed)
        self._thread_pool.start(worker)

    def _on_login(self) -> None:
        try:
            self._appstore.begin_interactive_login()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Авторизация", str(exc))
            return
        QMessageBox.information(
            self,
            "Авторизация",
            "Открыта консоль ipatool auth login.\n"
            "Введите Apple ID, пароль, Keychain passphrase и 2FA там.\n"
            "Дождитесь success=true.",
        )
        self.output.setPlainText(
            "Ожидание login в консоли… После success нажмите «Проверить сессию…»."
        )

    def _on_auth_info(self) -> None:
        try:
            self._appstore.begin_interactive_auth_info()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Сессия", str(exc))
            return
        QMessageBox.information(
            self,
            "Проверка сессии",
            "В консоли ipatool спросит Keychain passphrase "
            "(тот же локальный, что при login — не пароль Apple ID).\n"
            "Если увидите email/name и success — сессия активна.",
        )
        present = self._appstore.session_files_present()
        self.set_session_chip(present)
        self.output.setPlainText(
            "Открыта консоль auth info.\n"
            f"Локальные файлы сессии: {'да' if present else 'нет'}.\n"
            "Введите passphrase в консоли и смотрите success/email."
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
        if not self._appstore.session_files_present():
            QMessageBox.information(
                self,
                "Архив покупок",
                "Сначала войдите в App Store (кнопка «Войти…»), "
                "чтобы ipatool видел покупки этого Apple ID.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Архив покупок",
            "Открыть консоль дампа покупок?\n\n"
            "В консоли введите Keychain passphrase.\n"
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
        self._show_purchases_dialog(purchases)

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
        region_code = self.region_combo.currentData()
        if not region_code:
            QMessageBox.information(self, "Поиск", "Выберите регион App Store.")
            return
        self._set_busy(True, f"Умный поиск «{term}» ({region_code})…")
        worker = RegionalSearchAppWorker(self._smart_search, term, str(region_code))
        worker.signals.finished.connect(self._on_regional_search_results)
        worker.signals.failed.connect(self._on_worker_failed)
        self._thread_pool.start(worker)

    def _on_regional_search_results(self, results: object) -> None:
        assert isinstance(results, list)
        self._set_busy(False)
        region_code = self.region_combo.currentData()
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
        dialog.resize(1040, 620)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setStyleSheet(_DIALOG_QSS)
        pal = _light_dialog_palette()
        dialog.setPalette(pal)

        layout = QVBoxLayout(dialog)
        hint = QLabel(
            f"Каталог + iTunes ({region_code}). "
            "Пустые колонки скрыты. Полное название — в таблице и в блоке ниже "
            "(проверьте ID перед скачиванием). "
            "source=catalog может быть delisted; download только с лицензией."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Name + Store ID first so critical fields aren't squeezed away.
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
        _tune_data_table(table, name_col=0)
        layout.addWidget(table)
        detail = _make_selection_detail(dialog)
        layout.addWidget(detail)

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

        def _on_sel() -> None:
            app = _selected(quiet=True)
            if app is None:
                detail.setText("Выберите строку — здесь будет полное название и ID.")
                return
            detail.setText(
                f"{app.display_name or '—'}\n"
                f"Store ID: {app.store_id or '—'}\n"
                f"Bundle: {app.bundle_id or '—'}\n"
                f"Источник: {app.source or '—'} | "
                f"Seller: {app.seller_name or '—'} | "
                f"Версия: {app.version or '—'}"
            )

        table.itemSelectionChanged.connect(_on_sel)

        def on_use() -> None:
            app = _selected()
            if app is None:
                return
            self._apply_app_reference(app.store_id, app.bundle_id)
            self.search_input.clear()
            dialog.accept()
            self.output.setPlainText(
                f"ID из региона {region_code}: {app.display_name or '—'}\n"
                f"Подставлено в поле. Скачивание — только при лицензии на текущем ID.\n"
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
            self.try_purchase_check.setChecked(try_purchase.isChecked())
            self.search_input.clear()
            dialog.accept()
            ref = (
                AppReference(store_id=app.store_id)
                if app.store_id
                else AppReference(bundle_id=app.bundle_id)
            )
            self._start_download(ref, confirm=True)

        use_btn.clicked.connect(on_use)
        dl_btn.clicked.connect(on_download)
        buttons.rejected.connect(dialog.reject)
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
    ) -> None:
        try_purchase = self.try_purchase_check.isChecked()
        target = app.bundle_id or app.store_id or "?"
        version_line = (
            f"версия (external-version-id): {external_version_id}\n"
            if external_version_id
            else "версия: latest\n"
        )
        msg = (
            "Открыть консоль ipatool download?\n"
            f"{target}\n"
            f"{version_line}"
            f"Каталог: {self._packages_dir}\n"
            f"--purchase: {'да (текущий storefront)' if try_purchase else 'нет'}\n\n"
            "Нужна лицензия на текущем Apple ID. "
            "Поиск ID в другом регионе сам по себе лицензию не даёт.\n\n"
            "В консоли введите Keychain passphrase. "
            "После success — «Подхватить IPA»."
        )
        if confirm:
            answer = QMessageBox.question(self, "Загрузка", msg)
            if answer != QMessageBox.StandardButton.Yes:
                return
        before = self._appstore.list_ipa_names(self._packages_dir)
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
        self._download_before_names = before
        self.card_app.set_state("active", "Загрузка…")
        self.output.setPlainText(
            "Консоль download открыта.\n"
            "1) Введите Keychain passphrase в консоли\n"
            "2) Дождитесь success / DONE\n"
            "3) Нажмите «Подхватить IPA»\n\n"
            + (
                f"external-version-id={external_version_id}\n\n"
                if external_version_id
                else ""
            )
            + "Если в консоли license is required:\n"
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
        before = getattr(self, "_download_before_names", set())
        package = self._appstore.wait_for_new_ipa(
            self._packages_dir,
            before_names=before,
            timeout_sec=1.0,
        )
        if package is None:
            QMessageBox.information(
                self,
                "IPA",
                f"В {self._packages_dir} пока нет .ipa.\n"
                "Дождитесь окончания download в консоли и повторите.",
            )
            return
        self._on_download_done(package)

    def _on_install(self) -> None:
        if self._busy or self._package is None:
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
                f"iPhone: iOS {device.os_version or '?'}\n"
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
        self.output.setPlainText(
            "IPA подхвачен.\n"
            f"Путь: {package.local_path}\n"
            f"Размер: {package.size_bytes}\n"
            f"SHA-256: {package.sha256}\n"
            f"bundle_id: {package.bundle_id or 'не извлечён'}\n"
            f"version: {package.version or 'не извлечена'}\n"
            f"min iOS: {package.minimum_os_version or 'не извлечена'}\n"
            "Можно устанавливать на iPhone."
        )
        self._set_busy(False)

    def _on_install_done(self, payload: object) -> None:
        assert isinstance(payload, dict)
        self.output.setPlainText(
            "Инструмент установки сообщил об успехе.\n"
            f"Устройство: {payload.get('device_id')}\n"
            f"Пакет: {payload.get('package')}\n"
            "Запуск приложения на iPhone отдельно не проверялся."
        )
        self._set_busy(False)

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
            self.detect_button,
            self.pair_button,
            self.login_button,
            self.auth_info_button,
            self.logout_button,
            self.download_button,
            self.pickup_button,
            self.versions_button,
            self.pickup_versions_button,
            self.catalog_button,
            self.install_button,
            self.archive_button,
            self.pickup_archive_button,
            self.regional_search_button,
        ):
            if btn is self.install_button:
                btn.setEnabled((not busy) and self._package is not None)
            elif btn in (self.archive_button, self.pickup_archive_button, self.versions_button):
                btn.setEnabled((not busy) and session_ok)
            else:
                btn.setEnabled(not busy)
        if status:
            self.output.setPlainText(status)
