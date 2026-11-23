from pathlib import Path

from ios_restore.application.dependency_service import DependencyService


def test_check_reports_missing_script(tmp_path: Path) -> None:
    tools = tmp_path / "tools" / "libimobiledevice"
    tools.mkdir(parents=True)
    # Pretend we are portable root = tmp_path via tools_dir.
    svc = DependencyService(tools_dir=tools)
    # Monkeypatch project root used for catalog by pointing scripts parent correctly.
    report = svc.check()
    keys = {c.key for c in report.components}
    assert "ipatool" in keys
    assert "script:download-one.ps1" in keys or "script:download_one.py" in keys
    # Without files, those should be missing on a fresh tmp tree.
    assert not report.all_ok


def test_ensure_scripts_from_local_copy(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "portable"
    tools = root / "tools" / "libimobiledevice"
    tools.mkdir(parents=True)
    scripts = root / "tools"
    # Source checkout layout the service also searches.
    src_tools = tmp_path / "iCarcas" / "tools"
    src_tools.mkdir(parents=True)
    sample = src_tools / "download-one.ps1"
    sample.write_text("# test script\n", encoding="utf-8")

    svc = DependencyService(tools_dir=tools)
    monkeypatch.setattr(svc, "_root", root)
    monkeypatch.setattr(svc, "_scripts_dir", scripts)
    svc._ensure_scripts(["download-one.ps1"])
    assert (scripts / "download-one.ps1").is_file()
