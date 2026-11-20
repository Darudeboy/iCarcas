from __future__ import annotations

from pathlib import Path

from ios_restore.infrastructure.history_store import HistoryStore


def test_history_roundtrip(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "hist.json")
    store.record_download(
        ipa_path=str(tmp_path / "1_1.0.ipa"),
        store_id="1",
        display_name="Demo",
        version="1.0",
    )
    store.record_install(
        ipa_path=str(tmp_path / "1_1.0.ipa"),
        store_id="1",
        display_name="Demo",
        device_name="iPhone",
    )
    entries = store.list_entries()
    assert len(entries) == 2
    assert entries[0].kind == "install"
    assert entries[1].kind == "download"
    assert entries[1].display_name == "Demo"
