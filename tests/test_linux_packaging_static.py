from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_linux_release_pipeline_exists_and_is_platform_correct():
    build = (ROOT / "tools" / "build_linux_release.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'PLATFORM_KEY = "linux-x86_64"' in build
    assert "LifePlannerUpdater" in build
    assert "Linux_x86_64_Portable.tar.gz" in workflow
    assert "ubuntu-latest" in workflow
    assert "v2.2.63" in workflow
    assert "v1.0.3" in workflow
    assert "--allow-unsigned" in workflow
    assert "test ! -f release-linux/update-assets/lifeplanner-latest-linux.json.sig" in workflow
