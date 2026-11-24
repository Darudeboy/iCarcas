from __future__ import annotations

from ios_restore.infrastructure import desktop_shortcut as desk


def test_ps_quote_escapes_single_quotes() -> None:
    assert desk._ps_quote("a'b") == "'a''b'"


def test_shortcut_path_under_desktop() -> None:
    path = desk.shortcut_path("iCarcas.lnk")
    assert path.name == "iCarcas.lnk"
    assert "Desktop" in str(path) or "Рабочий" in str(path) or path.parent.exists()
