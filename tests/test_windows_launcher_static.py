from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_is_onefile_and_core_is_renamed() -> None:
    launcher_spec = (ROOT / "LifePlannerLauncher.spec").read_text(encoding="utf-8")
    core_spec = (ROOT / "LifePlanner.spec").read_text(encoding="utf-8")
    launcher = (ROOT / "windows_launcher.py").read_text(encoding="utf-8")
    assert 'name="LifePlanner"' in launcher_spec
    assert "COLLECT(" not in launcher_spec
    assert '"LifePlannerCore" if sys.platform.startswith("win") else "LifePlanner"' in core_spec
    assert 'name="LifePlanner"' in core_spec  # COLLECT directory remains stable
    assert "LifePlannerCore.exe" in launcher
    assert "nicht vollständig entpackt" in launcher
    assert "--diagnostics-file" in launcher


def test_core_update_asset_is_not_a_user_zip() -> None:
    windows_build = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
    linux_build = (ROOT / "tools/build_linux_release.py").read_text(encoding="utf-8")
    assert "LifePlanner_Core_{APP_VERSION}_Windows_x86_64.lpupdate" in windows_build
    assert "LifePlanner_Core_{APP_VERSION}_{PLATFORM_LABEL}.lpupdate" in linux_build
