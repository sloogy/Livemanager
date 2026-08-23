from __future__ import annotations

import json

import pytest

from lifeplanner_core import APP_VERSION
from lifeplanner_core.manifest import BridgeContract, ManifestError, ModuleManifest
from lifeplanner_core.process_manager import ModuleLaunchError, ModuleProcessManager


def _write_manifest(tmp_path, **overrides):
    data = {
        "schema": "lifeplanner.module.v2",
        "id": "demo",
        "name": "Demo",
        "version": "1.0.0",
        "description": "Testmodul",
        "requires_host": ">=0.5.15,<1.0",
        "source_entry": "main.py",
        "permissions": ["own_data_read", "bridge_write"],
        "environment": {"LIFEPLANNER_BRIDGE_DIR": "{bridge_dir}"},
        "bridge": {
            "publishes": [
                {
                    "name": "Demo Fokus",
                    "file": "demo_to_lifeplanner.jsonl",
                    "schemas": ["demo.focus.v1"],
                }
            ],
            "subscribes": [],
        },
    }
    data.update(overrides)
    path = tmp_path / "module.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_v2_manifest_persistiert_host_und_bridgevertrag(tmp_path):
    manifest = ModuleManifest.load(_write_manifest(tmp_path))
    assert manifest.schema == "lifeplanner.module.v2"
    assert manifest.requires_host == ">=0.5.15,<1.0"
    assert manifest.host_compatible("0.5.15")
    # Die Grenze ist das Manifest-Schema, nicht die Nebenversion des Hosts:
    # Ein Sprung 0.5 -> 0.6 hat die gesamte Suite entkoppelt, obwohl sich am
    # Vertrag nichts geaendert hatte. Ein neuer Vertrag heisst v3.
    assert manifest.host_compatible(APP_VERSION)
    assert not manifest.host_compatible("1.0.0")
    assert manifest.bridge_contracts == (
        BridgeContract(
            name="Demo Fokus",
            filename="demo_to_lifeplanner.jsonl",
            schemas=("demo.focus.v1",),
            direction="publish",
        ),
    )


def test_v2_manifest_ohne_hostanforderung_wird_abgelehnt(tmp_path):
    with pytest.raises(ManifestError, match="requires_host"):
        ModuleManifest.load(_write_manifest(tmp_path, requires_host=""))


def test_inzwischen_inkompatibles_installiertes_modul_startet_nicht(tmp_path):
    manifest = ModuleManifest.load(
        _write_manifest(tmp_path, requires_host=">=99.0")
    )
    manager = ModuleProcessManager()
    with pytest.raises(ModuleLaunchError, match="Benötigt LifePlanner"):
        manager.start(manifest, "default")
