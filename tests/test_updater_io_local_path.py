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
