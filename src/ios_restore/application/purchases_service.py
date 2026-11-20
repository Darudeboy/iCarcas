"""Сервис архива покупок App Store."""

from __future__ import annotations

from ios_restore.domain.models import PurchasedApp
from ios_restore.domain.ports import PurchasesPort


class PurchasesService:
    def __init__(self, adapter: PurchasesPort) -> None:
        self._adapter = adapter

    def list_purchases(self) -> list[PurchasedApp]:
        return self._adapter.list_purchases()
