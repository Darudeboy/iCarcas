"""Optional local storage of ipatool Keychain passphrase via Windows DPAPI."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

logger = logging.getLogger("ios_restore.keychain_passphrase")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def app_data_dir() -> Path:
    base = Path.home() / "AppData" / "Local" / "iCarcas"
    if sys.platform == "win32":
        local = Path.home() / "AppData" / "Local"
        if local.is_dir():
            base = local / "iCarcas"
    base.mkdir(parents=True, exist_ok=True)
    return base


def passphrase_path() -> Path:
    return app_data_dir() / "keychain_passphrase.dpapi"


def is_available() -> bool:
    return sys.platform == "win32"


def has_stored_passphrase() -> bool:
    path = passphrase_path()
    return path.is_file() and path.stat().st_size > 0


def clear_passphrase() -> None:
    path = passphrase_path()
    if path.is_file():
        path.unlink()
        logger.info("Cleared stored keychain passphrase")


def save_passphrase(passphrase: str) -> None:
    if not is_available():
        raise OSError("DPAPI passphrase storage is only supported on Windows.")
    text = (passphrase or "").strip()
    if not text:
        raise ValueError("Empty passphrase")
    blob = _dpapi_protect(text.encode("utf-8"))
    path = passphrase_path()
    path.write_bytes(blob)
    logger.info("Stored keychain passphrase under DPAPI at %s", path)


def load_passphrase() -> str | None:
    if not is_available() or not has_stored_passphrase():
        return None
    try:
        raw = passphrase_path().read_bytes()
        data = _dpapi_unprotect(raw)
        text = data.decode("utf-8").strip()
        return text or None
    except OSError as exc:
        logger.warning("Failed to unlock stored passphrase: %s", exc)
        return None


def _dpapi_protect(data: bytes) -> bytes:
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
