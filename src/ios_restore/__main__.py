"""Entry point: python -m ios_restore"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    from ios_restore.infrastructure.logging_setup import setup_logging

    setup_logging()

    # Headless demo for CI / quick check without showing a window.
    if "--demo-cli" in argv:
        return _run_cli_demo()

    from PySide6.QtWidgets import QApplication

    from ios_restore.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("iCarcas")
    app.setOrganizationName("iCarcas")
    window = MainWindow(packages_dir=Path.cwd() / "packages")
    window.show()
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
