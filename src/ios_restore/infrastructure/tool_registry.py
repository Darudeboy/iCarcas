"""Registry of expected external CLI tool names and version probes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    executable: str
    version_args: tuple[str, ...] = ("--version",)


KNOWN_TOOLS: dict[str, ToolSpec] = {
    "ipatool": ToolSpec(name="ipatool", executable="ipatool", version_args=("--version",)),
    "idevice_id": ToolSpec(name="idevice_id", executable="idevice_id", version_args=("-h",)),
    "ideviceinfo": ToolSpec(
        name="ideviceinfo", executable="ideviceinfo", version_args=("-h",)
    ),
    "ideviceinstaller": ToolSpec(
        name="ideviceinstaller",
        executable="ideviceinstaller",
        version_args=("--version",),
    ),
}


def required_tool_names() -> tuple[str, ...]:
    return tuple(KNOWN_TOOLS.keys())
