"""Check presence of bundled / PATH CLI tools."""

from __future__ import annotations

from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.infrastructure.paths import default_tools_dir, resolve_tool

# Stage-2 minimum for real device detection.
DEVICE_STAGE_TOOLS = (
    "idevice_id",
    "ideviceinfo",
    "idevicepair",
    "ideviceinstaller",
)


class EnvironmentCliAdapter:
    def __init__(self, tools_dir: Path | None = None) -> None:
        self._tools_dir = tools_dir or default_tools_dir()

    def check_tools(self) -> list[str]:
        ready: list[str] = []
        missing: list[str] = []
        for name in DEVICE_STAGE_TOOLS:
            path = resolve_tool(name, self._tools_dir)
            if path.is_file():
                ready.append(name)
            else:
                missing.append(name)
        if missing:
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                "Не найдены CLI для работы с устройством: "
                + ", ".join(missing)
                + f". Ожидаются в {self._tools_dir}",
            )
        ipatool = resolve_tool("ipatool", self._tools_dir)
        if not ipatool.is_file():
            raise RestoreError(
                ErrorCode.TOOL_NOT_FOUND,
                f"ipatool не найден в {self._tools_dir}",
            )
        ready.append("ipatool")
        return ready
