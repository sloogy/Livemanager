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


def test_module_runtime_is_executable_even_if_package_lost_the_bit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Some published .lpmodule packages record the runtime as 0644, which used
    # to make the installed module fail to start with "[Errno 13]".
    import os
    import sys

    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    (tmp_path / "app/modules").mkdir(parents=True)

    payload = tmp_path / "payload"
    runtime = payload / "Demo"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("#!/bin/sh\necho demo\n", encoding="utf-8")
    runtime.chmod(0o644)
    (payload / "main.py").write_text("print('demo')\n", encoding="utf-8")
    (payload / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": "demo",
                "name": "Demo-Modul",
                "version": "1.0.0",
                "description": "Testmodul",
                "source_entry": "main.py",
                "windows_executable": "Demo",
                "linux_executable": "Demo",
                "permissions": ["own_data_read"],
            }
        ),
        encoding="utf-8",
    )

    package = build_component_package(
        payload=payload,
        component_id="demo",
        name="Demo-Modul",
        version="1.0.0",
        kind="module",
        output=tmp_path / "demo.lpmodule",
        requires_host=">=0.4.0",
        platforms=(),
        private_key_b64="",
    )
    service = ModuleInstallerService(UpdateService(PluginLoadResult((), ())))
    info = service.inspect_package(package)

    installed_runtime = info.payload_dir / "Demo"
    if os.name != "nt":
        assert os.access(installed_runtime, os.X_OK)
    # Granting the bit must not invalidate the payload hash. The package is
    # unsigned, so staging needs the confirmation the module manager asks for
    # (Loop 34) - here it stands in for the user's Yes.
    assert info.signed is False
    staged = service.stage_package(info, vertrauen_bestaetigt=True)
    assert staged.tree_sha256 == info.payload_sha256


# ── Loop 34: Die Vertrauensregel gehoert ins Modell, nicht nur in den Dialog ──

def _unsigniertes_paket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    (tmp_path / "app/modules").mkdir(parents=True)
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
        private_key_b64="",
    )
    service = ModuleInstallerService(UpdateService(PluginLoadResult((), ())))
    return service, service.inspect_package(package)


def test_ein_unsigniertes_paket_kommt_nicht_ohne_bestaetigung_durch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bis Loop 34 stand diese Regel zweimal daneben statt einmal hier: als
    Rueckfrage im Modulverwalter und als harte Ablehnung im Bootstrap. Wer
    einen dritten Aufrufweg baut, haette sie nicht gehabt - und ein
    unsigniertes Modul ist ausfuehrbarer Code mit Benutzerrechten.
    """
    service, info = _unsigniertes_paket(tmp_path, monkeypatch)
    assert info.signed is False

    with pytest.raises(ModuleInstallerError):
        service.stage_package(info)


def test_die_bestaetigung_muss_ausdruecklich_sein(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Standardwert ist fail-closed, wie bei der Update-Signatur aus
    Loop 3: Nur wer die Frage tatsaechlich gestellt hat, darf ihn
    ueberschreiben."""
    service, info = _unsigniertes_paket(tmp_path, monkeypatch)

    staged = service.stage_package(info, vertrauen_bestaetigt=True)
    assert staged.tree_sha256 == info.payload_sha256


def test_ein_signiertes_paket_braucht_die_bestaetigung_nicht(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sonst waere die neue Huerde eine Huerde fuer alle - und der Anreiz,
    ueberhaupt zu signieren, waere weg."""
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_APP_DIR", str(tmp_path / "app"))
    (tmp_path / "app/modules").mkdir(parents=True)
    private, public = _keys()
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", public)
    package = build_component_package(
        payload=_module_payload(tmp_path / "payload"),
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
    assert service.stage_package(info).tree_sha256 == info.payload_sha256


def test_der_bootstrap_bestaetigt_niemals() -> None:
    """Er laeuft ohne Nutzer vor sich - dort kann niemand die Frage
    beantworten. Ein ``vertrauen_bestaetigt=True`` in dieser Datei waere ein
    stiller Weg an der Signaturpruefung vorbei."""
    from pathlib import Path as _Path

    quelle = (_Path(__file__).resolve().parents[1]
              / "lifeplanner_core" / "installer_bootstrap.py").read_text(encoding="utf-8")
    assert "vertrauen_bestaetigt" not in quelle
    assert "ist nicht signiert und wird abgelehnt" in quelle
