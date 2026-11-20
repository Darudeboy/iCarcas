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


def test_parse_purchases_ipatool_page_shape() -> None:
    text = """
    {
      "success": true,
      "totalCount": 2,
      "apps": [
        {"id": 1051293689, "bundleID": "com.ntvplus.matchclub", "name": "MATCH!", "version": "1.0"},
        {"id": "1475774929", "bundleID": "ru.mes.dnevnik", "name": "Дневник МЭШ", "version": "3.93.3"}
      ]
    }
    """
    apps = AppStoreCliAdapter._parse_purchases(text)
    assert len(apps) == 2
    assert apps[0].store_id == "1051293689"
    assert apps[0].bundle_id == "com.ntvplus.matchclub"
    assert apps[1].display_name == "Дневник МЭШ"


def test_parse_purchases_flat_array() -> None:
    text = '[{"appId":"1","bundleIdentifier":"a.b","title":"X"}]'
    apps = AppStoreCliAdapter._parse_purchases(text)
    assert len(apps) == 1
    assert apps[0].store_id == "1"
    assert apps[0].bundle_id == "a.b"


def test_load_purchases_dump(tmp_path: Path) -> None:
    dump = tmp_path / "purchases-dump.json"
    dump.write_text(
        '[{"id": 42, "bundleID": "com.demo", "name": "Demo"}]',
        encoding="utf-8",
    )
    apps = AppStoreCliAdapter().load_purchases_dump(dump)
    assert len(apps) == 1
    assert apps[0].store_id == "42"


def test_explain_download_failure_license() -> None:
    hint = AppStoreCliAdapter.explain_download_failure("license is required")
    assert "лицензии" in hint.lower() or "лицензия" in hint.lower()


def test_parse_versions_enriched() -> None:
    text = """
    {
      "success": true,
      "appId": "833449999",
      "externalVersionIdentifiers": ["100", "200"],
      "versions": [
        {"externalVersionId": "200", "displayVersion": "2.0", "releaseDate": "2024-01-01T00:00:00Z"},
        {"externalVersionId": "100", "displayVersion": "1.0", "releaseDate": null}
      ]
    }
    """
    versions = AppStoreCliAdapter._parse_versions(text)
    assert len(versions) == 2
    assert versions[0].external_version_id == "200"
    assert versions[0].display_version == "2.0"
    assert versions[1].display_version == "1.0"


def test_parse_versions_ids_only() -> None:
    text = '{"success":true,"externalVersionIdentifiers":["9","8"]}'
    versions = AppStoreCliAdapter._parse_versions(text)
    assert [v.external_version_id for v in versions] == ["9", "8"]


def test_load_versions_dump(tmp_path: Path) -> None:
    dump = tmp_path / "versions-1.json"
    dump.write_text(
        '{"versions":[{"externalVersionId":"42","displayVersion":"1.2"}]}',
        encoding="utf-8",
    )
    versions = AppStoreCliAdapter().load_versions_dump(dump)
    assert len(versions) == 1
    assert versions[0].external_version_id == "42"
