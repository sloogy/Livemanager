import json
from pathlib import Path

from lifeplanner_core.plugin_loader import discover_modules
from lifeplanner_core.process_manager import ModuleProcessManager
from lifeplanner_core.settings import SettingsStore
from lifeplanner_core.theme import (
    THEME_ENV_FILE,
    THEME_ENV_NAME,
    ThemeCatalog,
    build_stylesheet,
    publish_theme,
)

ROOT = Path(__file__).resolve().parents[1]


def _module(root: Path, module_id: str) -> None:
    path = root / module_id
    path.mkdir(parents=True)
    (path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (path / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": module_id,
                "name": module_id,
                "version": "1.0.0",
                "source_entry": "main.py",
                "permissions": ["own_data_read"],
            }
        ),
        encoding="utf-8",
    )


def test_bundled_profiles_load_without_errors():
    catalog = ThemeCatalog()
    assert catalog.errors == []
    names = catalog.names()
    assert "Standard - Hell" in names
    assert "Standard - Dunkel" in names
    # Die Profile stammen aus dem BudgetManager und müssen dort auffindbar bleiben.
    assert len(names) >= 20


def test_system_and_unknown_names_fall_back_to_a_real_profile():
    catalog = ThemeCatalog()
    assert catalog.resolve("system").name == "Standard - Hell"
    assert catalog.resolve("system", dark_hint=True).name == "Standard - Dunkel"
    assert catalog.resolve("gibt-es-nicht").name == "Standard - Hell"


def test_stylesheet_uses_the_profile_colours():
    profile = ThemeCatalog().resolve("Standard - Dunkel")
    sheet = build_stylesheet(profile)
    assert profile.color("hintergrund_app", "") in sheet
    assert profile.color("akzent", "") in sheet
    assert "{" in sheet and "}}" not in sheet


def test_apply_to_all_overrides_per_module_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    settings = SettingsStore(tmp_path / "settings.json")
    settings.set("theme", "Nord - Dunkel")
    settings.set_module_theme("budgetmanager", "Gruvbox - Hell")

    settings.set("theme_apply_to_all", True)
    assert settings.theme_for("budgetmanager") == "Nord - Dunkel"

    settings.set("theme_apply_to_all", False)
    assert settings.theme_for("budgetmanager") == "Gruvbox - Hell"
    # Module ohne eigene Wahl folgen weiterhin dem Host.
    assert settings.theme_for("fpm") == "Nord - Dunkel"


def test_module_environment_carries_the_central_theme(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "modules"
    _module(root, "budgetmanager")
    settings = SettingsStore(tmp_path / "settings.json")
    settings.set("theme", "Solarized - Dunkel")
    manifest = {m.module_id: m for m in discover_modules(root).modules}["budgetmanager"]
    manager = ModuleProcessManager(settings, ThemeCatalog())

    env = manager.build_environment(manifest, "default", {})

    assert env[THEME_ENV_NAME] == "Solarized - Dunkel"
    written = json.loads(Path(env[THEME_ENV_FILE]).read_text(encoding="utf-8"))
    assert written["schema"] == "lifeplanner.theme.v1"
    assert written["name"] == "Solarized - Dunkel"
    assert written["modus"] == "dunkel"
    assert written["farben"]["hintergrund_app"].startswith("#")


def test_module_environment_stays_clean_without_theme_wiring(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "modules"
    _module(root, "fpm")
    manifest = {m.module_id: m for m in discover_modules(root).modules}["fpm"]

    env = ModuleProcessManager().build_environment(manifest, "default", {})

    assert THEME_ENV_NAME not in env


def test_published_profile_is_replaced_not_appended(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    catalog = ThemeCatalog()
    first = publish_theme("default", "fpm", catalog.resolve("Standard - Hell"))
    second = publish_theme("default", "fpm", catalog.resolve("Standard - Dunkel"))
    assert first == second
    assert json.loads(second.read_text(encoding="utf-8"))["modus"] == "dunkel"
    assert not list(second.parent.glob("*.tmp"))


def test_release_build_ships_the_theme_profiles():
    spec = (ROOT / "LifePlanner.spec").read_text(encoding="utf-8")
    # Ohne die Profildateien im Build bliebe nur der eingebaute Notfallsatz.
    assert "lifeplanner_core" in spec and "themes" in spec
    assert '"themes"' in spec
    assert list((ROOT / "lifeplanner_core" / "themes").glob("*.json"))


def test_theme_directory_is_resolved_for_frozen_builds(monkeypatch, tmp_path):
    from lifeplanner_core.theme import bundled_theme_dir

    bundled = tmp_path / "themes"
    bundled.mkdir()
    monkeypatch.setattr("lifeplanner_core.theme.sys._MEIPASS", str(tmp_path), raising=False)
    assert bundled_theme_dir() == bundled


def test_shared_theme_uses_the_freizeitmanager_exchange_format(monkeypatch, tmp_path):
    """Der FreizeitManager liest bereits lifeplanner.theme.v1 aus dem Bridge-Ordner."""
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    from lifeplanner_core.paths import bridge_dir
    from lifeplanner_core.theme import SHARED_THEME_FILE, publish_shared_theme

    path = publish_shared_theme("default", ThemeCatalog().resolve("Nord - Dunkel"))

    assert path == bridge_dir("default") / SHARED_THEME_FILE
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["schema"] == "lifeplanner.theme.v1"
    assert record["name"] == "Nord - Dunkel"
    assert record["modus"] == "dunkel"
    assert record["gesetzt_von"] == "lifeplanner"
    assert isinstance(record["farben"], dict) and record["farben"]
    assert isinstance(record["schriftgroesse"], int)
    assert record["profil"] == "default"
