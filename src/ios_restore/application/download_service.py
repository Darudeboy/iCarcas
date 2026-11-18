from __future__ import annotations

from ios_restore.domain.models import AppReference, PackageInfo
from ios_restore.domain.ports import DownloadPort


class DownloadService:
    def __init__(self, adapter: DownloadPort) -> None:
        self._adapter = adapter

    def download(self, app: AppReference, destination_dir: str) -> PackageInfo:
        return self._adapter.download(app, destination_dir)
