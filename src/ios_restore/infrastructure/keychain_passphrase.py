"""Local storage of ipatool Keychain passphrase.

Windows: DPAPI blob under %LOCALAPPDATA%/iCarcas.
macOS/Linux: mode-0600 file under application support / XDG config.
Never uploaded — stays on this machine only.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("ios_restore.keychain_passphrase")


def app_data_dir() -> Path:
    if sys.platform == "win32":
        local = Path.home() / "AppData" / "Local"
        base = (local if local.is_dir() else Path.home()) / "iCarcas"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "iCarcas"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) / "icarcas" if xdg else Path.home() / ".config" / "icarcas"
    base.mkdir(parents=True, exist_ok=True)
    return base


def passphrase_path() -> Path:
    if sys.platform == "win32":
        return app_data_dir() / "keychain_passphrase.dpapi"
    return app_data_dir() / "keychain_passphrase"


def is_available() -> bool:
    return True


def has_stored_passphrase() -> bool:
    path = passphrase_path()
    return path.is_file() and path.stat().st_size > 0


def clear_passphrase() -> None:
    path = passphrase_path()
    if path.is_file():
        path.unlink()
        logger.info("Cleared stored keychain passphrase")


def save_passphrase(passphrase: str) -> None:
    text = (passphrase or "").strip()
    if not text:
        raise ValueError("Empty passphrase")
    path = passphrase_path()
    if sys.platform == "win32":
        blob = _dpapi_protect(text.encode("utf-8"))
        path.write_bytes(blob)
    else:
        path.write_text(text, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    logger.info("Stored keychain passphrase at %s", path)


def load_passphrase() -> str | None:
    if not has_stored_passphrase():
        return None
    path = passphrase_path()
    try:
        if sys.platform == "win32":
            data = _dpapi_unprotect(path.read_bytes())
            text = data.decode("utf-8").strip()
        else:
            text = path.read_text(encoding="utf-8").strip()
        return text or None
    except OSError as exc:
        logger.warning("Failed to unlock stored passphrase: %s", exc)
        return None


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    blob_in = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        "iCarcas ipatool keychain",
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    blob_in = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
