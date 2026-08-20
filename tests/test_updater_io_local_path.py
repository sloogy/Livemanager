from __future__ import annotations

from pathlib import Path

from lifeplanner_core.updater.io import _local_path


def test_local_path_detects_windows_drive_letter_paths():
    # urlparse() misreads a Windows drive letter ("C:\\...") as a one-letter
    # URL scheme; _local_path() must still recognize this as a local path.
    resolved = _local_path(r"C:\Users\runneradmin\AppData\Local\Temp\latest.json")
    assert resolved == Path(r"C:\Users\runneradmin\AppData\Local\Temp\latest.json")


def test_local_path_still_rejects_real_remote_schemes():
    assert _local_path("https://example.com/latest.json") is None
    assert _local_path("http://example.com/latest.json") is None


def test_local_path_handles_posix_paths():
    assert _local_path("/tmp/latest.json") == Path("/tmp/latest.json")


def test_secure_extract_zip_restores_executable_bit(tmp_path):
    # A module runtime such as modules/budgetmanager/BudgetManager/BudgetManager
    # must stay launchable after installation; otherwise starting the module
    # fails with "[Errno 13] Keine Berechtigung".
    import os
    import stat
    import zipfile

    from lifeplanner_core.updater.io import secure_extract_zip

    binary = tmp_path / "BudgetManager"
    binary.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    binary.chmod(0o755)
    plain = tmp_path / "module.json"
    plain.write_text("{}", encoding="utf-8")

    archive = tmp_path / "budgetmanager.lpmodule"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(binary, "payload/BudgetManager")
        handle.write(plain, "payload/module.json")

    destination = tmp_path / "installed"
    secure_extract_zip(archive, destination)

    extracted = destination / "payload" / "BudgetManager"
    if os.name != "nt":
        assert os.access(extracted, os.X_OK)
        # A plain data file must not become executable.
        assert not os.access(destination / "payload" / "module.json", os.X_OK)
        # Never carry setuid/setgid/sticky over from the archive.
        assert not stat.S_IMODE(extracted.stat().st_mode) & 0o7000
