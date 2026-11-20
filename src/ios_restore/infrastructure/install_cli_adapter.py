"""Install IPA via ideviceinstaller."""

from __future__ import annotations

import logging
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import DeviceInfo, PackageInfo
from ios_restore.infrastructure.paths import default_tools_dir, resolve_tool
from ios_restore.infrastructure.process_runner import ProcessRunner

logger = logging.getLogger("ios_restore.install")


class InstallCliAdapter:
    def __init__(
        self,
        runner: ProcessRunner | None = None,
        tools_dir: Path | None = None,
    ) -> None:
        self._runner = runner or ProcessRunner()
        self._tools_dir = tools_dir or default_tools_dir()

    def install(self, package: PackageInfo, device: DeviceInfo) -> None:
        installer = resolve_tool("ideviceinstaller", self._tools_dir)
        if not Path(installer).is_file():
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                "ideviceinstaller не найден.",
                details=str(self._tools_dir),
            )

        package_path = Path(package.local_path)
        if not package_path.is_file():
            raise RestoreError(
                ErrorCode.PACKAGE_INVALID,
                "Файл пакета для установки не найден.",
                details=str(package_path),
            )

        # ideviceinstaller 1.2+ uses subcommand `install`
        args = [
            str(installer),
            "-u",
            device.device_id,
            "install",
            str(package_path),
        ]
        result = self._runner.run(args, timeout=1800.0, check=False)
        if result.returncode != 0:
            # Fallback to legacy -i for older builds
            legacy = self._runner.run(
                [
                    str(installer),
                    "-u",
                    device.device_id,
                    "-i",
                    str(package_path),
                ],
                timeout=1800.0,
                check=False,
            )
            if legacy.returncode != 0:
                details = (result.stderr or result.stdout or legacy.stderr or legacy.stdout)[
                    :500
                ]
                raise RestoreError(
                    ErrorCode.INSTALL_FAILED,
                    "Инструмент установки сообщил об ошибке. "
                    "Это не доказывает и не опровергает запуск приложения.",
                    details=details,
                )
        logger.info("ideviceinstaller reported success for %s", package_path.name)
