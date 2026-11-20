"""Сервис поиска приложений в App Store."""

from __future__ import annotations

from ios_restore.domain.models import AppSearchResult
from ios_restore.domain.ports import SearchPort


class AppSearchService:
    def __init__(self, adapter: SearchPort) -> None:
        self._adapter = adapter

    def search(self, term: str) -> list[AppSearchResult]:
        return self._adapter.search(term)
