from __future__ import annotations

from ios_restore.domain.ports import EnvironmentPort


class EnvironmentService:
    def __init__(self, adapter: EnvironmentPort) -> None:
        self._adapter = adapter

    def verify(self) -> list[str]:
        return self._adapter.check_tools()
