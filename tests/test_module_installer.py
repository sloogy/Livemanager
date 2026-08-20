from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat

from lifeplanner_core.module_installer import ModuleInstallerError, ModuleInstallerService
from lifeplanner_core.plugin_loader import PluginLoadResult
from lifeplanner_core.updater.package_builder import build_component_package
from lifeplanner_core.updater.service import UpdateService


def _module_payload(root: Path, *, version: str = "1.0.0") -> Path:
    root.mkdir(parents=True)
    manifest = {
        "schema": "lifeplanner.module.v1",
        "id": "demo",
        "name": "Demo-Modul",
        "version": version,
        "description": "Testmodul",
        "source_entry": "main.py",
        "permissions": ["own_data_read"],
    }
    (root / "module.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "main.py").write_text("print('demo')\n", encoding="utf-8")
    return root


def _keys() -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(private_raw).decode("ascii"), base64.b64encode(public_raw).decode("ascii")


def test_signed_local_module_package_is_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    (tmp_path / "app/modules").mkdir(parents=True)
    private, public = _keys()
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", public)
    payload = _module_payload(tmp_path / "payload")
    package = build_component_package(
        payload=payload,
        component_id="demo",
        name="Demo-Modul",
        version="1.0.0",
        kind="module",
        output=tmp_path / "demo.lpmodule",
        requires_host=">=0.4.0",
        platforms=(),
        private_key_b64=private,
    )
    service = ModuleInstallerService(UpdateService(PluginLoadResult((), ())))
    info = service.inspect_package(package)
    assert info.signed is True
    assert info.compatible is True
    assert info.component_id == "demo"
    assert service.stage_package(info).tree_sha256 == info.payload_sha256


def test_tampered_signed_payload_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    (tmp_path / "app/modules").mkdir(parents=True)
    private, public = _keys()
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", public)
    original = build_component_package(
        payload=_module_payload(tmp_path / "payload"),
        component_id="demo",
        name="Demo-Modul",
        version="1.0.0",
        kind="module",
        output=tmp_path / "original.lpmodule",
        requires_host=">=0.4.0",
        private_key_b64=private,
    )
    tampered = tmp_path / "tampered.lpmodule"
    with zipfile.ZipFile(original, "r") as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "payload/main.py":
                data = b"print('tampered')\n"
            target.writestr(info, data)
    service = ModuleInstallerService(UpdateService(PluginLoadResult((), ())))
    with pytest.raises(ModuleInstallerError, match="Prüfsumme"):
        service.inspect_package(tampered)


def test_unsigned_package_requires_ui_trust_but_can_be_inspected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    (tmp_path / "app/modules").mkdir(parents=True)
    package = build_component_package(
        payload=_module_payload(tmp_path / "payload"),
        component_id="demo",
        name="Demo-Modul",
        version="1.0.0",
        kind="module",
        output=tmp_path / "demo.zip",
        requires_host=">=0.4.0",
    )
    service = ModuleInstallerService(UpdateService(PluginLoadResult((), ())))
    info = service.inspect_package(package)
    assert info.signed is False
    assert "Nicht signiert" in info.signature_status


def test_frozen_host_rejects_source_only_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lifeplanner_core.module_installer as installer_module

    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    monkeypatch.setattr(installer_module.sys, "frozen", True, raising=False)
    (tmp_path / "app/modules").mkdir(parents=True)
    package = build_component_package(
        payload=_module_payload(tmp_path / "payload"),
        component_id="demo",
        name="Demo-Modul",
        version="1.0.0",
        kind="module",
        output=tmp_path / "demo.lpmodule",
        requires_host=">=0.4.0",
    )
    service = ModuleInstallerService(UpdateService(PluginLoadResult((), ())))
    info = service.inspect_package(package)
    assert info.compatible is False
    assert "programmdatei" in info.compatibility_reason.lower()
