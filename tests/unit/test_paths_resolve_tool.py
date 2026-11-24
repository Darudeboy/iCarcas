from pathlib import Path

from ios_restore.infrastructure import paths as paths_mod


def test_resolve_tool_prefers_local(tmp_path: Path, monkeypatch) -> None:
    tools = tmp_path / "libimobiledevice"
    tools.mkdir()
    local = tools / "idevice_id"
    local.write_text("x", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "platform", "darwin")
    got = paths_mod.resolve_tool("idevice_id", tools)
    assert got == local


def test_resolve_tool_searches_brew_dirs(tmp_path: Path, monkeypatch) -> None:
    tools = tmp_path / "empty"
    tools.mkdir()
    brew_bin = tmp_path / "opt" / "homebrew" / "bin"
    brew_bin.mkdir(parents=True)
    brew_tool = brew_bin / "ideviceinfo"
    brew_tool.write_text("x", encoding="utf-8")
    brew_tool.chmod(0o755)

    monkeypatch.setattr(paths_mod.sys, "platform", "darwin")
    monkeypatch.setattr(paths_mod, "macos_brew_bin_dirs", lambda: (brew_bin,))
    monkeypatch.setattr(paths_mod.shutil, "which", lambda _name: None)

    got = paths_mod.resolve_tool("ideviceinfo", tools)
    assert got == brew_tool


def test_find_brew_in_extra_dirs(tmp_path: Path, monkeypatch) -> None:
    brew_bin = tmp_path / "opt" / "homebrew" / "bin"
    brew_bin.mkdir(parents=True)
    brew = brew_bin / "brew"
    brew.write_text("#!/bin/sh\n", encoding="utf-8")
    brew.chmod(0o755)

    monkeypatch.setattr(paths_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(paths_mod, "macos_brew_bin_dirs", lambda: (brew_bin,))
    assert paths_mod.find_brew() == brew
