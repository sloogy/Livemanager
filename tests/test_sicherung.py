"""Die Profilsicherung ist geschuetzt und begrenzt.

Jede Sicherung enthaelt den vollstaendigen Profilordner - Einstellungen,
Brueckendateien mit Buchungen und Sparzielen, Moduldaten. Sie ungeschuetzt
neben dem Profil abzulegen hoebe dessen 0700 wieder auf, und ohne Grenze
fuellt sich die Platte still.

Alle betroffenen Programme der Suite fuehren diesen Test unter demselben Namen.
"""

from __future__ import annotations

import os
import stat

import pytest

from lifeplanner_core.backup_service import (
    SICHERUNGEN_AUFBEWAHREN,
    create_profile_backup,
    verify_backup,
)

PROFIL = "probe"


@pytest.fixture()
def profil(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path))
    from lifeplanner_core.paths import backups_dir, profile_dir

    ordner = profile_dir(PROFIL)
    (ordner / "settings.json").write_text('{"theme": "system"}', encoding="utf-8")
    return backups_dir(PROFIL)


def test_die_sicherung_laesst_sich_pruefen(profil):
    pfad = create_profile_backup(PROFIL)
    manifest = verify_backup(pfad)
    assert manifest["profile_id"] == PROFIL
    assert manifest["file_count"] >= 1


@pytest.mark.skipif(os.name == "nt", reason="Windows kennt keine POSIX-Modi")
def test_die_sicherung_gehoert_nur_dem_eigentuemer(profil):
    pfad = create_profile_backup(PROFIL)
    assert stat.S_IMODE(pfad.stat().st_mode) == 0o600
    pruefsumme = pfad.with_suffix(pfad.suffix + ".sha256")
    assert stat.S_IMODE(pruefsumme.stat().st_mode) == 0o600


def test_alte_sicherungen_werden_aufgeraeumt(profil, monkeypatch):
    import lifeplanner_core.backup_service as dienst

    monkeypatch.setattr(dienst, "SICHERUNGEN_AUFBEWAHREN", 3)
    for nummer in range(6):
        (profil / f"lifeplanner-{PROFIL}-2026010{nummer}-000000.zip").touch()
    create_profile_backup(PROFIL)

    verblieben = sorted(profil.glob(f"lifeplanner-{PROFIL}-*.zip"))
    assert len(verblieben) == 3, [p.name for p in verblieben]


def test_fremde_dateien_bleiben_unangetastet(profil, monkeypatch):
    """Was jemand von Hand dort abgelegt hat, passt nicht auf das Muster."""
    import lifeplanner_core.backup_service as dienst

    monkeypatch.setattr(dienst, "SICHERUNGEN_AUFBEWAHREN", 1)
    eigene = profil / "mein_wichtiges_backup.zip"
    eigene.write_text("von Hand", encoding="utf-8")
    for nummer in range(4):
        (profil / f"lifeplanner-{PROFIL}-2026010{nummer}-000000.zip").touch()

    create_profile_backup(PROFIL)

    assert eigene.is_file()


def test_ein_anderes_profil_bleibt_unberuehrt(profil, monkeypatch, tmp_path):
    """Aufgeraeumt wird nur innerhalb des eigenen Profils."""
    import lifeplanner_core.backup_service as dienst

    monkeypatch.setattr(dienst, "SICHERUNGEN_AUFBEWAHREN", 1)
    fremd = profil / "lifeplanner-anderes-20260101-000000.zip"
    fremd.touch()
    for nummer in range(3):
        (profil / f"lifeplanner-{PROFIL}-2026010{nummer}-000000.zip").touch()

    create_profile_backup(PROFIL)

    assert fremd.is_file()
