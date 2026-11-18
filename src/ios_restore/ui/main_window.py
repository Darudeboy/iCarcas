"""Main window: device detection, App Store via interactive ipatool console, install."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ios_restore.domain.models import AppReference, DeviceInfo, PackageInfo
from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter
from ios_restore.infrastructure.device_cli_adapter import DeviceCliAdapter
from ios_restore.infrastructure.environment_cli_adapter import EnvironmentCliAdapter
from ios_restore.infrastructure.install_cli_adapter import InstallCliAdapter
from ios_restore.infrastructure.paths import default_tools_dir
from ios_restore.ui.theme import STYLESHEET
from ios_restore.ui.workers import (
    DetectDevicesWorker,
    InstallAppWorker,
    PairDeviceWorker,
)

ROW_H = 34


def _panel() -> QFrame:
    frame = QFrame()
    frame.setObjectName("panel")
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return frame


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionLabel")
    return label


def _btn(text: str, *, object_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if object_name:
        button.setObjectName(object_name)
    button.setFixedHeight(ROW_H)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return button


def _equal_buttons(*buttons: QPushButton) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.setContentsMargins(0, 0, 0, 0)
    for button in buttons:
        row.addWidget(button, 1)
    return row


class MainWindow(QMainWindow):
    def __init__(self, packages_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("iCarcas")
        self.resize(820, 720)
        self.setMinimumSize(700, 600)
        self.setStyleSheet(STYLESHEET)
        self._layout_fitted = False

        self._thread_pool = QThreadPool.globalInstance()
        self._packages_dir = packages_dir or (Path.cwd() / "packages")
        self._busy = False
        self._devices: list[DeviceInfo] = []
        self._package: PackageInfo | None = None
        tools = default_tools_dir()
        self._device_adapter = DeviceCliAdapter(tools_dir=tools)
        self._appstore = AppStoreCliAdapter(tools_dir=tools)
        self._installer = InstallCliAdapter(tools_dir=tools)

        central = QWidget(self)
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        root.addLayout(self._build_header())
        root.addWidget(self._build_device_panel())
        root.addWidget(self._build_account_panel())
        root.addWidget(self._build_app_panel())
        root.addWidget(self._build_log_panel(), 1)

        self._append_env_status()
        QTimer.singleShot(0, self._fit_window_to_content)

    def _fit_window_to_content(self) -> None:
        if self._layout_fitted:
            return
        self._layout_fitted = True
        # Ensure content panels keep full height (no crush/overlap).
        for panel in self.findChildren(QFrame):
            if panel.objectName() != "panel":
                continue
            if panel is self.output.parent():
                continue
            panel.setMinimumHeight(panel.sizeHint().height())
        needed = self.sizeHint().height()
        self.setMinimumHeight(max(self.minimumHeight(), needed))
        if self.height() < needed:
            self.resize(self.width(), needed)

    def _build_header(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        col.setContentsMargins(2, 0, 2, 6)

        title = QLabel()
        title.setObjectName("brandTitle")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setText(
            '<span style="color:#1A73E8;">i</span>'
            '<span style="color:#121417;">Carcas</span>'
        )
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        col.addWidget(title)

        tag = QLabel("Восстановление своих приложений на iPhone")
        tag.setObjectName("brandTagline")
        col.addWidget(tag)
        return col

    def _build_device_panel(self) -> QFrame:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(_section("Устройство"))

        self.detect_button = _btn("Найти устройство")
        self.detect_button.clicked.connect(self._on_detect)
        self.pair_button = _btn("Установить доверие")
        self.pair_button.clicked.connect(self._on_pair)
        layout.addLayout(_equal_buttons(self.detect_button, self.pair_button))
        return panel

    def _build_account_panel(self) -> QFrame:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(_section("App Store"))

        hint = QLabel(
            "Вход и загрузка открывают консоль ipatool — "
            "пароль, 2FA и Keychain passphrase только там."
        )
        hint.setObjectName("brandTagline")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.login_button = _btn("Войти…")
        self.login_button.clicked.connect(self._on_login)
        self.auth_info_button = _btn("Проверить сессию…")
        self.auth_info_button.clicked.connect(self._on_auth_info)
        self.logout_button = _btn("Выйти…", object_name="dangerButton")
        self.logout_button.clicked.connect(self._on_logout)
        layout.addLayout(
            _equal_buttons(self.login_button, self.auth_info_button, self.logout_button)
        )
        return panel

    def _build_app_panel(self) -> QFrame:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(_section("Приложение"))

        self.app_input = QLineEdit()
        self.app_input.setObjectName("appInput")
        self.app_input.setPlaceholderText(
            "Bundle id (com.example.app) или App Store ID"
        )
        placeholder_palette = self.app_input.palette()
        placeholder_palette.setColor(
            QPalette.ColorRole.PlaceholderText, QColor("#5C6670")
        )
        placeholder_palette.setColor(QPalette.ColorRole.Text, QColor("#121417"))
        self.app_input.setPalette(placeholder_palette)
        self.app_input.setFixedHeight(ROW_H)
        layout.addWidget(self.app_input)

        self.download_button = _btn("Скачать IPA…")
        self.download_button.clicked.connect(self._on_download)
        self.pickup_button = _btn("Подхватить IPA")
        self.pickup_button.clicked.connect(self._on_pickup_ipa)
        layout.addLayout(_equal_buttons(self.download_button, self.pickup_button))

        self.install_button = _btn("Установить на iPhone", object_name="primaryButton")
        self.install_button.clicked.connect(self._on_install)
        self.install_button.setEnabled(False)
        layout.addWidget(self.install_button)
        return panel

    def _build_log_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(_section("Журнал"))

        self.output = QTextEdit()
        self.output.setObjectName("logView")
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(120)
        layout.addWidget(self.output, 1)
        return panel

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
            self.output.setPlainText("Устройства не найдены.")
        else:
            lines = [f"Найдено устройств: {len(devices)}"]
            for d in devices:
                avail = "доступно" if d.available_for_operations else "нужно доверие"
                lines.append(
                    f"- {d.display_name} | UDID={d.device_id} | "
                    f"iOS={d.os_version or '?'} | {avail}"
                )
            self.output.setPlainText("\n".join(lines))
        self._set_busy(False)

    def _on_paired(self, device: object) -> None:
        assert isinstance(device, DeviceInfo)
        self._devices = [device]
        self.output.setPlainText(
            "Доверие OK.\n"
            f"{device.display_name} | {device.device_id} | iOS {device.os_version or '?'}"
        )
        self._set_busy(False)

    def _on_download_done(self, package: PackageInfo) -> None:
        self._package = package
        self.install_button.setEnabled(True)
        self.install_button.setText("Установить на iPhone")
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
                btn.setText("Установить на iPhone")
            else:
                btn.setEnabled(not busy)
        if status:
            self.output.setPlainText(status)
