from __future__ import annotations

from pathlib import Path

from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter


def test_parse_json_blob_line() -> None:
    text = (
        "noise\n"
        '{"email":"a@b.c","name":"Demo","storefront":"RUS","success":true}\n'
    )
    payload = AppStoreCliAdapter._parse_json_blob(text)
    assert payload is not None
    assert payload["email"] == "a@b.c"


def test_list_ipa_names(tmp_path: Path) -> None:
    (tmp_path / "a.ipa").write_bytes(b"PK")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    names = AppStoreCliAdapter().list_ipa_names(tmp_path)
    assert names == {"a.ipa"}
