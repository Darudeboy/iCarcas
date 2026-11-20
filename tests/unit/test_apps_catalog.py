from pathlib import Path

from ios_restore.infrastructure.apps_catalog import filter_catalog, load_apps_catalog


def test_load_apps_catalog_sample(tmp_path: Path) -> None:
    catalog = tmp_path / "apps_catalog.txt"
    catalog.write_text(
        "Zvuk: 833449999\n"
        "Автодор: 1497865709\n"
        "# comment\n"
        "broken line\n"
        "Dup: 833449999\n",
        encoding="utf-8",
    )
    apps = load_apps_catalog(catalog)
    assert len(apps) == 2
    assert apps[0].store_id == "833449999"
    assert apps[1].display_name == "Автодор"


def test_filter_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "apps_catalog.txt"
    catalog.write_text(
        "Zvuk: 833449999\n"
        "MAX: 6739530834\n"
        "Альфа-Банк (Оригинал): 353127685\n",
        encoding="utf-8",
    )
    apps = load_apps_catalog(catalog)
    assert len(filter_catalog(apps, "max")) == 1
    assert len(filter_catalog(apps, "8334")) == 1
    assert filter_catalog(apps, "") == apps
    alfa = filter_catalog(apps, "Alfabank")
    assert len(alfa) == 1
    assert alfa[0].store_id == "353127685"


def test_repo_catalog_loads() -> None:
    apps = load_apps_catalog()
    assert len(apps) > 100
    ids = {a.store_id for a in apps}
    assert "1497865709" in ids  # Автодор
    assert "6739530834" in ids  # MAX
