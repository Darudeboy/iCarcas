"""Main window: device detection, App Store via interactive ipatool console, install."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ios_restore.domain.models import AppReference, DeviceInfo, PackageInfo
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
)


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
        self.auth_info_button = make_button("Проверить сессию…")
        self.auth_info_button.clicked.connect(self._on_auth_info)
        self.logout_button = make_button("Выйти…", "danger")
        self.logout_button.clicked.connect(self._on_logout)
        row.addWidget(self.login_button, 1)
        row.addWidget(self.auth_info_button, 1)
        row.addWidget(self.logout_button, 1)
        self.card_store.body.addLayout(row)
        root.addWidget(self.card_store)

        self.card_app = Card("Приложение", step=3)
        self.app_input = QLineEdit()
        self.app_input.setPlaceholderText(
            "Bundle id (com.example.app) или App Store ID"
        )
        self.app_input.setClearButtonEnabled(True)
        self.card_app.body.addWidget(self.app_input)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.download_button = make_button("Скачать IPA…")
        self.download_button.clicked.connect(self._on_download)
        self.pickup_button = make_button("Подхватить IPA")
        self.pickup_button.clicked.connect(self._on_pickup_ipa)
        row.addWidget(self.download_button, 1)
        row.addWidget(self.pickup_button, 1)
        self.card_app.body.addLayout(row)
        self.install_button = make_button("Установить на iPhone", "primary")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._on_install)
        self.card_app.body.addWidget(self.install_button)
        root.addWidget(self.card_app)

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

    def _on_download(self) -> None:
        raw = self.app_input.text().strip()
        if not raw:
            QMessageBox.information(self, "Приложение", "Укажите bundle id или App Store ID.")
            return
        app = self._parse_app_reference(raw)
        answer = QMessageBox.question(
            self,
            "Загрузка",
            "Открыть консоль ipatool download?\n"
            f"{app.bundle_id or app.store_id}\n"
            f"Каталог: {self._packages_dir}\n\n"
            "В консоли введите Keychain passphrase. "
            "После success нажмите «Подхватить IPA».",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        before = self._appstore.list_ipa_names(self._packages_dir)
        try:
            self._appstore.begin_interactive_download(app, str(self._packages_dir))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Загрузка", str(exc))
            return
        self._download_before_names = before
        self.card_app.set_state("active", "Загрузка…")
        self.output.setPlainText(
            "Консоль download открыта.\n"
            "1) Введите Keychain passphrase в консоли\n"
            "2) Дождитесь success / DONE\n"
            "3) Нажмите «Подхватить IPA»"
        )

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
        answer = QMessageBox.question(
            self,
            "Подтверждение установки",
            "Установить пакет на устройство?\n\n"
            f"Устройство: {device.display_name} ({device.device_id})\n"
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
        self.output.setPlainText(message)
        self._set_busy(False)

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self._busy = busy
        for btn in (
            self.detect_button,
            self.pair_button,
            self.login_button,
            self.auth_info_button,
            self.logout_button,
            self.download_button,
            self.pickup_button,
            self.install_button,
        ):
            if btn is self.install_button:
                btn.setEnabled((not busy) and self._package is not None)
            else:
                btn.setEnabled(not busy)
        if status:
            self.output.setPlainText(status)
