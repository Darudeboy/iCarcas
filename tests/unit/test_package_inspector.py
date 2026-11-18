from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.infrastructure.package_inspector import PackageInspector


def _write_ipa(path: Path, *, plist_xml: str, member: str = "Payload/Demo.app/Info.plist") -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member, plist_xml.encode("utf-8"))
        zf.writestr("Payload/Demo.app/demo", b"binary")
    path.write_bytes(buf.getvalue())


def test_inspect_valid_ipa(tmp_path: Path) -> None:
    ipa = tmp_path / "app.ipa"
    plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.example.demo</string>
<key>CFBundleShortVersionString</key><string>1.2.3</string>
<key>MinimumOSVersion</key><string>15.0</string>
</dict></plist>
"""
    _write_ipa(ipa, plist_xml=plist)
    info = PackageInspector().inspect(str(ipa))
    assert info.bundle_id == "com.example.demo"
    assert info.version == "1.2.3"
    assert info.minimum_os_version == "15.0"
    assert len(info.sha256) == 64


def test_reject_non_zip(tmp_path: Path) -> None:
    bad = tmp_path / "x.ipa"
    bad.write_bytes(b"not-a-zip")
    with pytest.raises(RestoreError) as exc:
        PackageInspector().inspect(str(bad))
    assert exc.value.code == ErrorCode.PACKAGE_INVALID


def test_reject_zip_slip(tmp_path: Path) -> None:
    ipa = tmp_path / "slip.ipa"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", b"nope")
    ipa.write_bytes(buf.getvalue())
    with pytest.raises(RestoreError) as exc:
        PackageInspector().inspect(str(ipa))
    assert exc.value.code == ErrorCode.PACKAGE_INVALID
    assert "Zip Slip" in exc.value.message


def test_missing_metadata_is_none(tmp_path: Path) -> None:
    ipa = tmp_path / "empty.ipa"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Payload/Demo.app/binary", b"x")
    ipa.write_bytes(buf.getvalue())
    info = PackageInspector().inspect(str(ipa))
    assert info.bundle_id is None
    assert info.version is None
