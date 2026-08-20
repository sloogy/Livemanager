import json
from pathlib import Path

from lifeplanner_core.process_manager import ModuleProcessManager
from lifeplanner_core.manifest import ModuleManifest


def test_generic_module_data_and_bridge_environment(tmp_path, monkeypatch):
    module = tmp_path / "demo"
    module.mkdir()
    (module / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (module / "module.json").write_text(json.dumps({
        "schema":"lifeplanner.module.v1", "id":"demo", "name":"Demo", "version":"1.0.0",
        "source_entry":"main.py", "permissions":["own_data_read"]
    }), encoding="utf-8")
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    manifest = ModuleManifest.load(module / "module.json")
    env = ModuleProcessManager().build_environment(manifest, "default", {})
    assert env["LIFEPLANNER_MODULE_DATA_DIR"].endswith("modules/demo")
    assert env["LIFEPLANNER_BRIDGE_DIR"].endswith("bridge")
    assert env["LIFEPLANNER_CENTRAL_UPDATER"] == "1"
