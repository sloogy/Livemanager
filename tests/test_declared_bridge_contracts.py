from __future__ import annotations

import json

from lifeplanner_core.bridge import summarize_declared_bridges
from lifeplanner_core.manifest import BridgeContract, ModuleManifest


def test_neue_modul_outbox_braucht_keinen_core_sonderfall(tmp_path, monkeypatch):
    import lifeplanner_core.bridge as bridge

    monkeypatch.setattr(bridge, "bridge_dir", lambda _profile: tmp_path)
    target = tmp_path / "freizeitmanager_to_lifeplanner.jsonl"
    target.write_text(
        json.dumps({"schema": "freizeitmanager.focus.manifest.v1"})
        + "\n"
        + json.dumps(
            {
                "schema": "freizeitmanager.focus.v1",
                "kind": "next_step",
                "name": "Patrick",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = ModuleManifest(
        module_id="freizeitmanager",
        name="FreizeitManager",
        version="0.1.10",
        description="",
        source_entry="main.py",
        requires_host=">=0.5.15,<1.0",
        schema="lifeplanner.module.v2",
        bridge_contracts=(
            BridgeContract(
                name="FreizeitManager Fokus → LifePlanner",
                filename=target.name,
                schemas=("freizeitmanager.focus.v1",),
                direction="publish",
            ),
        ),
    )

    findings = summarize_declared_bridges("default", [manifest])
    assert len(findings) == 1
    assert findings[0].module_id == "freizeitmanager"
    assert findings[0].eintraege == 1
    assert findings[0].ungueltige_zeilen == 0
