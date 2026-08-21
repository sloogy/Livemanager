import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_linux_release_pipeline_exists_and_is_platform_correct():
    build = (ROOT / "tools" / "build_linux_release.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'PLATFORM_KEY = "linux-x86_64"' in build
    assert "LifePlannerUpdater" in build
    assert "Linux_x86_64_Portable.tar.gz" in workflow
    assert "ubuntu-latest" in workflow
    # Der Workflow muss genau die Refs ziehen, die in der Lockdatei stehen.
    # Frueher stand hier ein fester Tag - der blieb fuenf Modulstaende lang
    # stehen, waehrend der Host laengst neuere Module haette bauen sollen.
    lock = json.loads((ROOT / "dependencies/modules.lock.json").read_text(encoding="utf-8"))
    for modul in lock["modules"]:
        assert f"'{modul['default_ref']}'" in workflow, (
            f"{modul['id']}: Workflow zieht nicht {modul['default_ref']}"
        )
    # Der Erst-Release ging bewusst unsigniert heraus. Seither prueft der
    # Updater fail-closed: ein Release ohne Signatur waere fuer jede
    # installierte Fassung tot.
    assert "--allow-unsigned" not in workflow
    assert "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64" in workflow
    assert "test -f release-linux/update-assets/lifeplanner-latest-linux.json.sig" in workflow
