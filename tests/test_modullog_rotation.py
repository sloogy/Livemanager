"""Modul-Logs wachsen nicht unbegrenzt.

Der Host gibt jedem Modulprozess einen Dateideskriptor, in den dieser seine
Ausgaben schreibt. Ein RotatingFileHandler hilft dort nicht - der Modulprozess
weiss nichts von Python-Logging. Also wird beim Start gerollt.

Ohne das wuchs die Datei bei jedem Start weiter; ein Modul, das im
Sekundentakt etwas ausgibt, fuellt so unbemerkt die Platte.
"""

from __future__ import annotations

from lifeplanner_core.process_manager import (
    MAX_MODULLOG_BYTES,
    MODULLOG_STAENDE,
    _rotiere_modullog,
)


def _fuellen(pfad, groesse: int) -> None:
    pfad.write_bytes(b"x" * groesse)


def test_ein_kleines_log_bleibt_liegen(tmp_path):
    pfad = tmp_path / "fpm.log"
    _fuellen(pfad, 100)
    _rotiere_modullog(pfad)
    assert pfad.stat().st_size == 100
    assert not list(tmp_path.glob("fpm.log.*"))


def test_ein_grosses_log_wird_beiseitegelegt(tmp_path):
    pfad = tmp_path / "fpm.log"
    _fuellen(pfad, MAX_MODULLOG_BYTES + 1)
    _rotiere_modullog(pfad)
    assert not pfad.exists(), "das alte Log liegt noch am selben Platz"
    assert (tmp_path / "fpm.log.1").stat().st_size == MAX_MODULLOG_BYTES + 1


def test_die_staende_schieben_sich_durch(tmp_path):
    pfad = tmp_path / "fpm.log"
    for runde in range(3):
        _fuellen(pfad, MAX_MODULLOG_BYTES + 1)
        pfad.write_bytes(f"runde {runde}".encode() + b"x" * MAX_MODULLOG_BYTES)
        _rotiere_modullog(pfad)
    assert (tmp_path / "fpm.log.1").read_bytes().startswith(b"runde 2")
    assert (tmp_path / "fpm.log.2").read_bytes().startswith(b"runde 1")
    assert (tmp_path / "fpm.log.3").read_bytes().startswith(b"runde 0")


def test_mehr_als_die_erlaubten_staende_entstehen_nicht(tmp_path):
    pfad = tmp_path / "fpm.log"
    for _ in range(MODULLOG_STAENDE + 4):
        _fuellen(pfad, MAX_MODULLOG_BYTES + 1)
        _rotiere_modullog(pfad)
    assert len(list(tmp_path.glob("fpm.log.*"))) == MODULLOG_STAENDE


def test_eine_fehlende_datei_ist_kein_fehler(tmp_path):
    """Der erste Start eines Moduls - da gibt es noch nichts zu rollen."""
    _rotiere_modullog(tmp_path / "gibtsnicht.log")
