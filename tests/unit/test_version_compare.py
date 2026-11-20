from ios_restore.domain.version_compare import (
    compare_versions,
    device_meets_minimum,
    parse_version_tuple,
)


def test_parse_version_tuple() -> None:
    assert parse_version_tuple("17.5.1") == (17, 5, 1)
    assert parse_version_tuple("15.0") == (15, 0)
    assert parse_version_tuple(None) is None
    assert parse_version_tuple("abc") is None


def test_compare_versions() -> None:
    assert compare_versions("17.5", "15.0") == 1
    assert compare_versions("14.8", "15.0") == -1
    assert compare_versions("15.0", "15.0.0") == 0
    assert compare_versions("17.5", None) is None


def test_device_meets_minimum() -> None:
    assert device_meets_minimum("17.2", "15.0") is True
    assert device_meets_minimum("14.0", "15.0") is False
    assert device_meets_minimum("17.2", None) is None
