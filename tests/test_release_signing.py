from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from tools.release_signing import ReleaseSigning, resolve_package_private_key, resolve_release_signing


def _keys() -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(private_raw).decode("ascii"), base64.b64encode(public_raw).decode("ascii")


def test_release_requires_keys_or_explicit_unsigned_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", raising=False)
    monkeypatch.delenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", raising=False)
    with pytest.raises(RuntimeError, match="--allow-unsigned"):
        resolve_release_signing(allow_unsigned=False)

    signing = resolve_release_signing(allow_unsigned=True)
    assert signing.unsigned is True


def test_unsigned_mode_rejects_ambiguous_signing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", "configured")
    monkeypatch.delenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", raising=False)
    with pytest.raises(RuntimeError, match="darf nicht zusammen"):
        resolve_release_signing(allow_unsigned=True)
    with pytest.raises(RuntimeError, match="darf nicht zusammen"):
        resolve_package_private_key(allow_unsigned=True, private_key_b64="configured")


def test_signed_mode_validates_matching_key_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    private, public = _keys()
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", private)
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", public)
    signing = resolve_release_signing(allow_unsigned=False)
    assert signing.private_key_b64 == private
    assert signing.public_key_b64 == public


def test_package_builder_requires_explicit_unsigned_mode() -> None:
    with pytest.raises(RuntimeError, match="--allow-unsigned"):
        resolve_package_private_key(allow_unsigned=False, private_key_b64="")
    assert resolve_package_private_key(allow_unsigned=True, private_key_b64="") == ""


def _release_shell(root: Path) -> Path:
    shell = root / "shell"
    module = shell / "modules" / "demo"
    module.mkdir(parents=True)
    (shell / "LifePlanner").write_bytes(b"core")
    (module / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": "demo",
                "name": "Demo",
                "version": "1.0.0",
                "description": "Demo-Modul",
                "source_entry": "main.py",
                "permissions": ["own_data_read"],
            }
        ),
        encoding="utf-8",
    )
    (module / "main.py").write_text("print('demo')\n", encoding="utf-8")
    return shell


@pytest.mark.parametrize(
    ("module_name", "builder_name", "release_attribute"),
    [
        ("tools.build_release", "_build_update_assets", "RELEASE"),
        ("tools.build_linux_release", "build_update_assets", "RELEASE"),
    ],
)
def test_release_builders_create_explicitly_unsigned_module_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    builder_name: str,
    release_attribute: str,
) -> None:
    import importlib

    release_module = importlib.import_module(module_name)
    release_dir = tmp_path / module_name.rsplit(".", 1)[-1]
    monkeypatch.setattr(release_module, release_attribute, release_dir)
    builder = getattr(release_module, builder_name)
    builder(_release_shell(tmp_path / builder_name), signing=ReleaseSigning("", ""))

    packages = tuple((release_dir / "update-assets").glob("*.lpmodule"))
    assert len(packages) == 1
    with zipfile.ZipFile(packages[0]) as archive:
        assert "component.json" in archive.namelist()
        assert "component.json.sig" not in archive.namelist()
    assert not tuple((release_dir / "update-assets").glob("*.sig"))
