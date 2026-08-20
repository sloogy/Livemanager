from lifeplanner_core.backup_service import create_profile_backup, verify_backup
from lifeplanner_core.paths import module_data_dir


def test_profile_backup(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path))
    data = module_data_dir("default", "fpm")
    (data / "example.txt").write_text("hello", encoding="utf-8")
    backup = create_profile_backup("default")
    assert backup.is_file()
    manifest = verify_backup(backup)
    assert manifest["profile_id"] == "default"
    assert manifest["file_count"] == 1
