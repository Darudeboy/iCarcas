from PySide6.QtCore import QSettings

from ios_restore.ui.tos import TOS_VERSION, accept_tos, tos_accepted


def test_tos_gate(tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "tos.ini"), QSettings.Format.IniFormat)
    assert not tos_accepted(settings)
    accept_tos(settings)
    assert tos_accepted(settings)
    assert str(settings.value("tos/accepted_version")) == TOS_VERSION
