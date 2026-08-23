"""Der Host wird typgeprueft.

Bis Loop 57 lief mypy nur im BudgetManager. Der LifePlanner startet Prozesse,
installiert Module und prueft Signaturen - dort faellt ein Typfehler nicht als
falsche Anzeige auf, sondern als abgebrochener Update-Lauf.

Die Einfuehrung kostete vier echte Funde, alle in der Art "der Typ ist weiter
als das, was damit gemacht wird":

* ``log_handle: object`` - und darauf wurde ``close()`` aufgerufen.
* ``value: object`` - und daraus wurde ein Tupel gebaut.
* Zweimal ``QApplication.instance().styleHints()``: ``styleHints()`` gehoert
  zu ``QGuiApplication`` und ist statisch. Der Umweg ueber ``instance()`` war
  laenger, nicht sicherer.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Was geprueft wird. Waechst - darf nie schrumpfen.
GEPRUEFT = ("lifeplanner_core",)


def test_mypy_ini_existiert() -> None:
    """Ohne sie gilt die Konfiguration des Entwicklerrechners."""
    assert (ROOT / "mypy.ini").is_file()


def test_mypy_ist_exakt_gepinnt() -> None:
    """Eine neue Nebenversion urteilt anders - und dann faellt ein Gate um,
    ohne dass sich eine Zeile Code geaendert hat (Befund aus Loop 35)."""
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert re.search(r"(?m)^mypy==\d+\.\d+\.\d+$", text), "mypy nicht exakt gepinnt"


def test_die_stubs_fuer_requests_sind_dabei() -> None:
    """Sonst meldet mypy den fehlenden Stub als Fehler.

    Die Alternative waere eine Ausnahme in mypy.ini - die aber auch echte
    Fehler in diesem Bereich verschlucken wuerde.
    """
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "types-requests" in text


def test_das_release_gate_prueft_typen() -> None:
    quelle = (ROOT / "tools" / "validate_release.py").read_text(encoding="utf-8")
    assert '"mypy"' in quelle, "validate_release.py ruft mypy nicht auf"
    for ziel in GEPRUEFT:
        assert ziel in quelle, f"{ziel} steht nicht im Gate"


def test_mypy_laeuft_sauber_durch() -> None:
    """Der Zustand selbst, nicht nur die Einrichtung.

    Achtung beim lokalen Lauf: ohne PySide6 in der Umgebung sind alle
    Qt-Typen ``Any`` und der Lauf ist gruen und wertlos. Darum
    ``tools/gepinnte_werkzeuge.py`` - es bringt die Abhaengigkeiten mit.
    """
    ergebnis = subprocess.run(
        [sys.executable, "-m", "mypy", *GEPRUEFT],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr
