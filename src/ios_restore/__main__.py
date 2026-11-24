"""Entry point: python -m ios_restore"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Frozen macOS .app: worker spawns use sys.executable (this launcher) with a
    # bundled helper script as argv[0]. Re-enter that script instead of the GUI.
    if sys.platform == "darwin" and getattr(sys, "frozen", False) and argv:
        from ios_restore.infrastructure.paths import default_tools_dir

        helpers = default_tools_dir().parent
        script = Path(argv[0])
        if script.name in {
            "download_one.py",
            "list_versions_dump.py",
            "list_purchases_dump.py",
        }:
            try:
                same = script.is_absolute() and script.resolve() == (
                    helpers / script.name
                ).resolve()
            except OSError:
                same = False
            if same:
                import runpy

                sys.argv = argv
                runpy.run_path(str(script), run_name="__main__")
                return 0

    from ios_restore.infrastructure.logging_setup import setup_logging

    setup_logging()

    # Headless demo for CI / quick check without showing a window.
    if "--demo-cli" in argv:
        return _run_cli_demo()

    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from ios_restore.ui import apple_ui as aui
    from ios_restore.ui.brand_icon import BrandSplash, load_app_icon
    from ios_restore.ui.main_window import MainWindow
    from ios_restore.ui.theme import PALETTES, build_palette

    settings = QSettings("iCarcas", "iCarcas")
    if "--light" in argv:
        mode = "light"
    elif "--dark" in argv:
        mode = "dark"
    else:
        saved = str(settings.value("theme", "dark"))
        mode = saved if saved in ("light", "dark") else "dark"

    app = QApplication(sys.argv)
    app.setApplicationName("iCarcas")
    app.setOrganizationName("iCarcas")
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(
        [
            "SF Pro Text",
            "Segoe UI Variable Text",
            "Segoe UI",
            "Helvetica Neue",
            "Arial",
        ]
    )
    font.setPixelSize(13)
    app.setFont(font)

    # Theme BEFORE any window — changing QSS after show() re-polishes and flickers.
    aui.set_theme(mode)
    if mode in PALETTES:
        app.setPalette(build_palette(mode))
    app.setStyleSheet(aui.qss())

    app_icon = load_app_icon()
    app.setWindowIcon(app_icon)

    skip_splash = "--no-splash" in argv

    # Pixmap splash (bitmap) — no empty framed QWidget flash on Windows.
    splash: BrandSplash | None = None
    if not skip_splash:
        splash = BrandSplash(mode=mode)
        splash.show_cover()

    from PySide6.QtCore import Qt

    from ios_restore.infrastructure.paths import default_packages_dir

    window = MainWindow(packages_dir=default_packages_dir(), mode=mode)
    window.setWindowIcon(app_icon)
    # Keep the native main HWND off-screen until splash handoff.
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

    def _activate_main() -> None:
        from ios_restore.ui import apple_ui as aui

        aui._reveal_tree(window)  # noqa: SLF001
        if not window.isVisible():
            window.show()
        window.raise_()
        window.activateWindow()

    if skip_splash or splash is None:
        _activate_main()
    else:
        splash._on_finished = _activate_main  # noqa: SLF001
        splash.start_brand(handoff_window=window)
        app._icarcas_splash = splash  # type: ignore[attr-defined]

    return app.exec()


def _run_cli_demo() -> int:
    from ios_restore.application.restore_service import RestoreService
    from ios_restore.domain.models import AppReference, OperationStatus
    from ios_restore.infrastructure.mock_adapters import (
        MockAuthAdapter,
        MockDeviceAdapter,
        MockDownloadAdapter,
        MockEnvironmentAdapter,
        MockInstallAdapter,
    )
    from ios_restore.ui.view_models import present_demo_result

    packages = Path.cwd() / "packages"
    service = RestoreService(
        environment=MockEnvironmentAdapter(),
        devices=MockDeviceAdapter(),
        auth=MockAuthAdapter(),
        download=MockDownloadAdapter(output_root=packages),
        install=MockInstallAdapter(),
        packages_dir=packages,
    )
    result = service.run_demo_scenario(
        AppReference(bundle_id="com.example.demo", display_name="Demo App"),
        confirm_install=True,
    )
    view = present_demo_result(result)
    print(view.detail_text)
    return 0 if result.operation.status == OperationStatus.SUCCEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
