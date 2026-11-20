from PySide6.QtCore import QSettings

from ios_restore.ui.onboarding import (
    ONBOARDING_VERSION,
    mark_onboarding_done,
    onboarding_done,
)
from ios_restore.ui.tos import accept_tos, tos_accepted


def test_onboarding_flag(tmp_path) -> None:
    settings = QSettings(str(tmp_path / "o.ini"), QSettings.Format.IniFormat)
    assert not onboarding_done(settings)
    mark_onboarding_done(settings)
    assert onboarding_done(settings)
    assert str(settings.value("onboarding/completed_version")) == ONBOARDING_VERSION


def test_tos_still_independent(tmp_path) -> None:
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    assert not tos_accepted(settings)
    accept_tos(settings)
    assert tos_accepted(settings)
