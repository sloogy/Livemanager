
from lifeplanner_core import paths


def test_data_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "lp"))
    assert paths.data_root() == (tmp_path / "lp").resolve()


def test_profile_paths_are_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path))
    a = paths.module_data_dir("default", "budgetmanager")
    b = paths.module_data_dir("default", "fpm")
    assert a != b
    assert a.parent == b.parent
