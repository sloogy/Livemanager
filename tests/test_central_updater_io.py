from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from lifeplanner_core.updater.io import UpdateIOError, secure_extract_zip, tree_sha256


def test_secure_zip_extract_and_tree_hash(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("component.json", "{}")
        zf.writestr("payload/file.txt", "hello")
    target = tmp_path / "out"
    secure_extract_zip(archive, target)
    assert (target / "payload/file.txt").read_text() == "hello"
    assert len(tree_sha256(target / "payload")) == 64


def test_secure_zip_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    with pytest.raises(UpdateIOError):
        secure_extract_zip(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()
