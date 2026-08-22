"""Meldungen der Module fürs Dashboard einsammeln.

Der Host zeigte bisher, ob die Module laufen und wie viele Zeilen in den
Brückendateien stehen. Was in einem Modul gerade schiefläuft — ein
überzogenes Budget, ein Füller, der seit Wochen ungespült steht, ein Freund,
den man lange nicht gesehen hat — stand nur dort und war nur zu sehen, wenn
man das Modul öffnete. Dabei ist der Host das Fenster, das ohnehin offen ist.

Gelesen wird ``lifeplanner.notice.v1``: eine Datei je Modul im Brückenordner,
mit einer Kopfzeile und je Meldung einer Zeile.

**Der Host bewertet nichts.** Er sortiert und zeigt an. Die Dringlichkeit
kommt vom Modul, das die Daten hat — nur der BudgetManager weiß, was „80 %
verbraucht" bei dieser Kategorie in diesem Monat bedeutet. Alles andere wäre
eine zweite Fachlogik neben der ersten, die auseinanderläuft.

Meldungen sind **Anzeige, keine Daten**: Sie tragen eine Überschrift, einen
Zusatz und eine Dringlichkeit. Kein Betrag, keine Buchung, kein Kontaktname
als Datensatz.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .bridge_registry import bekannte_ordner
from .paths import bridge_dir

MANIFEST_SCHEMA = "lifeplanner.notice.manifest.v1"
NOTICE_SCHEMA = "lifeplanner.notice.v1"
DATEI_MUSTER = "*_notices.jsonl"

# Aufsteigend nach Dringlichkeit. Was ein Modul darüber hinaus schickt, wird
# als "info" gezeigt statt verworfen: Eine unbekannte Stufe ist ein neueres
# Modul, kein Fehler.
DRINGLICHKEITEN = ("info", "warnung", "kritisch")
STANDARD_DRINGLICHKEIT = "info"

# Auch über alle Module hinweg gedeckelt. Ein Dashboard, das man scrollen
# muss, wird nicht gelesen.
HOECHSTZAHL = 50

# Ein Modul, das eine 40-MB-Datei schreibt, darf den Host nicht anhalten.
GROESSENGRENZE = 2 * 1024 * 1024


@dataclass(frozen=True)
class Meldung:
    """Eine Zeile im Dashboard."""

    modul: str
    kennung: str
    dringlichkeit: str
    ueberschrift: str
    zusatz: str = ""
    bereich: str = ""

    @property
    def rang(self) -> int:
        return DRINGLICHKEITEN.index(self.dringlichkeit)


@dataclass(frozen=True)
class MeldungsBefund:
    """Was beim Einsammeln herauskam."""

    meldungen: tuple[Meldung, ...]
    gelesene_dateien: int
    ungueltige_zeilen: int
    verworfene: int = 0

    @property
    def anzahl(self) -> int:
        return len(self.meldungen)

    def nach_dringlichkeit(self, stufe: str) -> tuple[Meldung, ...]:
        return tuple(m for m in self.meldungen if m.dringlichkeit == stufe)


def _modulname(kopf: dict, pfad: Path) -> str:
    name = str(kopf.get("module") or "").strip()
    if name:
        return name
    # Ohne Kopfzeile bleibt der Dateiname: besser eine grobe Zuordnung als
    # eine Meldung ohne Absender.
    return pfad.stem.removesuffix("_notices")


def _lies_datei(pfad: Path) -> tuple[list[Meldung], int]:
    """Meldungen einer Datei, plus Zahl der unlesbaren Zeilen."""
    try:
        if pfad.stat().st_size > GROESSENGRENZE:
            return [], 1
        zeilen = pfad.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return [], 1

    modul = pfad.stem.removesuffix("_notices")
    meldungen: list[Meldung] = []
    ungueltig = 0
    for zeile in zeilen:
        if not zeile.strip():
            continue
        try:
            eintrag = json.loads(zeile)
        except json.JSONDecodeError:
            ungueltig += 1
            continue
        if not isinstance(eintrag, dict):
            ungueltig += 1
            continue

        schema = eintrag.get("schema")
        if schema == MANIFEST_SCHEMA:
            modul = _modulname(eintrag, pfad)
            continue
        if schema != NOTICE_SCHEMA:
            ungueltig += 1
            continue

        ueberschrift = str(eintrag.get("headline") or "").strip()
        if not ueberschrift:
            # Eine Meldung ohne Überschrift wäre eine leere Zeile im
            # Dashboard - die sagt weniger als gar keine.
            ungueltig += 1
            continue

        dringlichkeit = str(eintrag.get("urgency") or STANDARD_DRINGLICHKEIT)
        if dringlichkeit not in DRINGLICHKEITEN:
            dringlichkeit = STANDARD_DRINGLICHKEIT

        meldungen.append(
            Meldung(
                modul=modul,
                kennung=str(eintrag.get("id") or ""),
                dringlichkeit=dringlichkeit,
                ueberschrift=ueberschrift,
                zusatz=str(eintrag.get("detail") or ""),
                bereich=str(eintrag.get("area") or ""),
            )
        )
    return meldungen, ungueltig


def sammle_meldungen(profile_id: str) -> MeldungsBefund:
    """Liest die Meldungen aller Module aus allen bekannten Brückenordnern.

    Aus *allen* bekannten, nicht nur dem aktiven: Wer ein Modul mal
    eigenständig und mal im Host startet, hat zwei Brücken (siehe
    ``bridge_registry``). Der aktive Ordner kommt zuletzt, damit bei gleicher
    Kennung gewinnt, was hier und jetzt gilt.
    """
    aktiv = bridge_dir(profile_id)
    gesehen: dict[tuple[str, str], Meldung] = {}
    dateien = 0
    ungueltig = 0

    for ordner in bekannte_ordner(aktiv):
        try:
            pfade = sorted(ordner.glob(DATEI_MUSTER))
        except OSError:
            # Ein getrenntes Netzlaufwerk ist kein Grund, das Dashboard
            # leer zu lassen - die anderen Ordner gelten weiter.
            continue
        for pfad in pfade:
            meldungen, fehler = _lies_datei(pfad)
            dateien += 1
            ungueltig += fehler
            for meldung in meldungen:
                schluessel = (meldung.modul, meldung.kennung or meldung.ueberschrift)
                gesehen[schluessel] = meldung

    geordnet = sorted(
        gesehen.values(),
        key=lambda m: (-m.rang, m.modul, m.ueberschrift),
    )
    sichtbar = tuple(geordnet[:HOECHSTZAHL])
    return MeldungsBefund(
        meldungen=sichtbar,
        gelesene_dateien=dateien,
        ungueltige_zeilen=ungueltig,
        verworfene=len(geordnet) - len(sichtbar),
    )
