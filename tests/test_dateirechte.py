"""Der Profilordner liegt nicht offen auf der Platte.

Er traegt die Einstellungen, die Bruecke zwischen den Modulen und deren
Datenverzeichnisse. Mit dem Standard-umask angelegt ist er auf typischen
Linux-Systemen 0755 - jedes lokale Konto kann hineinsehen, und in der Bruecke
stehen Buchungen und Sparziele.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""

from __future__ import annotations

import os
import stat

import pytest

from lifeplanner_core.file_permissions import (
    OWNER_ONLY_DIR,
    OWNER_ONLY_FILE,
    is_world_accessible,
    secure_dir,
    secure_file,
)

posix_only = pytest.mark.skipif(
    os.name == "nt", reason="Windows kennt keine POSIX-Modi; dort greifen ACLs"
)


@posix_only
def test_ein_neues_profil_gehoert_nur_dem_eigentuemer(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path))
    from lifeplanner_core.paths import bridge_dir, profile_dir

    ordner = profile_dir("probe")
    assert stat.S_IMODE(ordner.stat().st_mode) == OWNER_ONLY_DIR
    # Die Bruecke liegt darunter und ist damit ebenfalls nicht erreichbar.
    assert bridge_dir("probe").is_relative_to(ordner)


@posix_only
def test_secure_file_nimmt_gruppe_und_anderen_die_rechte(tmp_path):
    pfad = tmp_path / "offen.txt"
    pfad.write_text("geheim", encoding="utf-8")
    os.chmod(pfad, 0o644)
    assert is_world_accessible(pfad)

    assert secure_file(pfad) is True
    assert stat.S_IMODE(pfad.stat().st_mode) == OWNER_ONLY_FILE
    assert not is_world_accessible(pfad)


@posix_only
def test_secure_dir_schliesst_den_ordner(tmp_path):
    ordner = tmp_path / "daten"
    ordner.mkdir(mode=0o755)
    assert secure_dir(ordner) is True
    assert stat.S_IMODE(ordner.stat().st_mode) == OWNER_ONLY_DIR


def test_eine_fehlende_datei_ist_kein_fehler(tmp_path):
    assert secure_file(tmp_path / "gibtsnicht") is False


def test_der_inhalt_bleibt_lesbar(tmp_path):
    pfad = tmp_path / "datei.txt"
    pfad.write_text("inhalt", encoding="utf-8")
    secure_file(pfad)
    assert pfad.read_text(encoding="utf-8") == "inhalt"
