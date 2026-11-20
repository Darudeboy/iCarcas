from pathlib import Path

from ios_restore.application.diagnostics_service import DiagnosticsService, mask_udid
from ios_restore.infrastructure.logging_setup import redact_secrets


def test_mask_udid() -> None:
    assert mask_udid("00008120-000974560A87C01E").startswith("0000")
    assert "…" in mask_udid("00008120-000974560A87C01E")


def test_diagnostics_zip_has_no_ipa(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "secret.ipa").write_bytes(b"PK")
    out = tmp_path / "diag.zip"
    svc = DiagnosticsService(
        packages_dir=packages,
        session_present=True,
        devices=[{"device_id": "ABCD1234EFGH5678", "display_name": "Phone"}],
        log_text="passphrase=supersecret download ok",
    )
    svc.build_zip(out)
    assert out.is_file()
    import zipfile

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "meta.json" in names
        assert "ui-log-redacted.txt" in names
        assert not any(n.endswith(".ipa") for n in names)
        log = zf.read("ui-log-redacted.txt").decode("utf-8")
        assert "supersecret" not in log
        assert "***" in redact_secrets("passphrase=supersecret")


def test_explain_504() -> None:
    from ios_restore.infrastructure.appstore_cli_adapter import AppStoreCliAdapter

    hint = AppStoreCliAdapter.explain_download_failure("HTTP 504 gateway timeout")
    assert "504" in hint
