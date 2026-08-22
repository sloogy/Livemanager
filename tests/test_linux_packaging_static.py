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
    # Der Workflow darf kein Modul-Ref mehr selbst tragen. Frueher stand hier
    # ein fester Tag; nachgezogen wurde er per Regex in die Workflow-Datei -
    # wofuer der Release-Token das Recht "workflows" braucht, das er nicht hat.
    # Jetzt liest der Workflow die Refs zur Laufzeit aus der Lockdatei.
    lock = json.loads((ROOT / "dependencies/modules.lock.json").read_text(encoding="utf-8"))
    assert "tools/module_sources.py --github-env" in workflow
    for modul in lock["modules"]:
        assert f"'{modul['default_ref']}'" not in workflow, (
            f"{modul['id']}: Ref steht wieder fest im Workflow"
        )
        assert f"env.LOCK_{modul['ref_variable']}" in workflow, (
            f"{modul['id']}: Workflow liest das Ref nicht aus der Lockdatei"
        )
    # Der Erst-Release ging bewusst unsigniert heraus. Seither prueft der
    # Updater fail-closed: ein Release ohne Signatur waere fuer jede
    # installierte Fassung tot.
    assert "--allow-unsigned" not in workflow
    assert "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64" in workflow
    assert "test -f release-linux/update-assets/lifeplanner-latest-linux.json.sig" in workflow
