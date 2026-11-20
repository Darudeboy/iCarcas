from pathlib import Path

import pytest

from ios_restore.infrastructure import keychain_passphrase as kc


def test_passphrase_roundtrip_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not kc.is_available():
        pytest.skip("DPAPI only on Windows")
    monkeypatch.setattr(kc, "app_data_dir", lambda: tmp_path)
    assert not kc.has_stored_passphrase()
    kc.save_passphrase("secret-pass")
    assert kc.has_stored_passphrase()
    assert kc.load_passphrase() == "secret-pass"
    kc.clear_passphrase()
    assert not kc.has_stored_passphrase()
    assert kc.load_passphrase() is None


def test_empty_passphrase_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not kc.is_available():
        pytest.skip("DPAPI only on Windows")
    monkeypatch.setattr(kc, "app_data_dir", lambda: tmp_path)
    with pytest.raises(ValueError):
        kc.save_passphrase("  ")
