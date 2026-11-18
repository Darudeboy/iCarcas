"""Safe IPA / zip package inspection."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.models import PackageInfo

MAX_PACKAGE_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB
MAX_ZIP_ENTRIES = 50_000
MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024  # 8 GiB


class PackageInspector:
    def inspect(self, path: str) -> PackageInfo:
        package_path = Path(path)
        if not package_path.is_file():
            raise RestoreError(
                ErrorCode.PACKAGE_INVALID,
                "Файл пакета не найден.",
                details=str(package_path),
            )

        size = package_path.stat().st_size
        if size <= 0 or size > MAX_PACKAGE_BYTES:
            raise RestoreError(
                ErrorCode.PACKAGE_INVALID,
                "Размер пакета вне допустимых пределов.",
            )

        if not zipfile.is_zipfile(package_path):
            raise RestoreError(
                ErrorCode.PACKAGE_INVALID,
                "Файл не является ZIP/IPA-архивом.",
            )

        bundle_id: str | None = None
        version: str | None = None
        minimum_os: str | None = None

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                self._validate_zip_safety(zf)
                app_plist = self._find_info_plist(zf)
                if app_plist is not None:
                    raw = zf.read(app_plist)
                    bundle_id = _extract_plist_string(raw, "CFBundleIdentifier")
                    version = _extract_plist_string(raw, "CFBundleShortVersionString")
                    minimum_os = _extract_plist_string(raw, "MinimumOSVersion")
        except RestoreError:
            raise
        except zipfile.BadZipFile as exc:
            raise RestoreError(
                ErrorCode.PACKAGE_INVALID,
                "Повреждённый архив пакета.",
                details=str(exc),
            ) from exc

        sha256 = _sha256_file(package_path)
        return PackageInfo(
            local_path=str(package_path.resolve()),
            size_bytes=size,
            sha256=sha256,
            bundle_id=bundle_id,
            version=version,
            minimum_os_version=minimum_os,
        )

    def _validate_zip_safety(self, zf: zipfile.ZipFile) -> None:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise RestoreError(
                ErrorCode.PACKAGE_INVALID,
                "Слишком много элементов в архиве.",
            )
        total_uncompressed = 0
        for info in infos:
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or name.startswith("../") or "/../" in name:
                raise RestoreError(
                    ErrorCode.PACKAGE_INVALID,
                    "Небезопасный путь внутри архива (Zip Slip).",
                    details=name,
                )
            # Zip info flag bit 0x20 / external_attr symlink heuristics vary;
            # reject obvious absolute / traversal paths and runaway size.
            total_uncompressed += max(info.file_size, 0)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise RestoreError(
                    ErrorCode.PACKAGE_INVALID,
                    "Суммарный размер распаковки превышает лимит.",
                )

    @staticmethod
    def _find_info_plist(zf: zipfile.ZipFile) -> str | None:
        candidates = [
            name
            for name in zf.namelist()
            if name.replace("\\", "/").endswith(".app/Info.plist")
            and name.replace("\\", "/").startswith("Payload/")
        ]
        if not candidates:
            return None
        # Prefer shallowest Payload/*.app/Info.plist
        candidates.sort(key=lambda n: n.count("/"))
        return candidates[0]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_plist_string(data: bytes, key: str) -> str | None:
    """Best-effort XML plist string extraction without executing content."""
    text = data.decode("utf-8", errors="replace")
    needle = f"<key>{key}</key>"
    idx = text.find(needle)
    if idx < 0:
        return None
    rest = text[idx + len(needle) :]
    start = rest.find("<string>")
    end = rest.find("</string>")
    if start < 0 or end < 0 or end <= start:
        return None
    value = rest[start + len("<string>") : end].strip()
    return value or None
