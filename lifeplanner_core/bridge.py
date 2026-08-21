from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import bridge_dir

# Die drei Dateien, über die FPM und BudgetManager sich verständigen. Der Host
# schreibt keine davon - er liest mit, damit sichtbar wird, ob der Austausch
# überhaupt stattfindet.
FPM_TO_BUDGETMANAGER = "fpm_to_budgetmanager.jsonl"
BUDGETMANAGER_TO_FPM = "budgetmanager_to_fpm.jsonl"
BUDGETMANAGER_SAVINGS_GOALS = "budgetmanager_savings_goals.jsonl"

# Ein Manifest steht als erste Zeile in jeder Datei und zählt nicht als Eintrag.
_MANIFEST_SCHEMAS = {
    "budgetmanager.import.manifest.v1",
    "fpm.import.manifest.v1",
    "fpm.savings-goals.manifest.v1",
    "fpm.savings_goals.manifest.v1",
}

# BudgetManager schreibt Sparziele mit Bindestrich, ältere Fassungen mit
# Unterstrich. Beide gelten, sonst meldet der Host eine leere Brücke, wo in
# Wahrheit Daten liegen.
_SAVINGS_GOAL_SCHEMAS = {"fpm.savings-goal.v1", "fpm.savings_goal.v1"}
_EXPENSE_SCHEMAS = {"fpm.import.v1", "fpm.expense.v1"}


@dataclass(frozen=True)
class DateiBefund:
    """Was in einer der drei Brückendateien steht."""

    name: str
    pfad: Path
    vorhanden: bool
    eintraege: int
    summe: float
    waehrungen: tuple[str, ...]
    ungueltige_zeilen: int

    @property
    def leer(self) -> bool:
        return self.vorhanden and self.eintraege == 0


@dataclass(frozen=True)
class BridgeSummary:
    """Der Zustand der Brücke insgesamt.

    Die fünf erstgenannten Felder gab es schon, als nur die FPM-Richtung
    gelesen wurde; sie bleiben, damit bestehende Aufrufer weiterlaufen.
    """

    fpm_records: int
    fpm_total: float
    currencies: tuple[str, ...]
    invalid_lines: int
    source_path: Path
    # Neu: die Gegenrichtung und die Sparziel-Spiegelung.
    fpm_nach_budgetmanager: DateiBefund | None = None
    budgetmanager_nach_fpm: DateiBefund | None = None
    sparziele: DateiBefund | None = None

    @property
    def dateien(self) -> tuple[DateiBefund, ...]:
        return tuple(
            befund
            for befund in (
                self.fpm_nach_budgetmanager,
                self.budgetmanager_nach_fpm,
                self.sparziele,
            )
            if befund is not None
        )

    @property
    def gesamt_eintraege(self) -> int:
        return sum(befund.eintraege for befund in self.dateien)


def _lies(pfad: Path, name: str, gueltige_schemas: set[str]) -> DateiBefund:
    """Zählt die gültigen Einträge einer JSONL-Datei.

    Eine fehlende Datei ist kein Fehler: Sie bedeutet, dass das jeweilige
    Programm noch nichts geschrieben hat. Genau diese Unterscheidung - fehlt
    versus leer versus fehlerhaft - macht sichtbar, an welcher Stelle der
    Austausch hakt.
    """
    if not pfad.is_file():
        return DateiBefund(name, pfad, False, 0, 0.0, (), 0)

    eintraege = 0
    summe = 0.0
    ungueltig = 0
    waehrungen: set[str] = set()
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
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
        if schema in _MANIFEST_SCHEMAS:
            continue
        if schema not in gueltige_schemas:
            ungueltig += 1
            continue
        eintraege += 1
        betrag = eintrag.get("amount")
        if betrag is None:
            # Sparziele tragen keinen Betrag, sondern ein Ziel.
            betrag = eintrag.get("target_amount")
        try:
            summe += float(betrag or 0)
        except (TypeError, ValueError):
            ungueltig += 1
        waehrungen.add(str(eintrag.get("currency") or "CHF"))
    return DateiBefund(
        name,
        pfad,
        True,
        eintraege,
        round(summe, 2),
        tuple(sorted(waehrungen)),
        ungueltig,
    )


def summarize_fpm_outbox(profile_id: str) -> BridgeSummary:
    """Liest alle drei Brückendateien des Profils.

    Der Host las lange nur die FPM-Richtung. Wenn BudgetManager seine
    Sparziele nicht herausschrieb, war das hier nicht zu sehen - die Anzeige
    meldete unauffällig einen Stand, der nur die halbe Brücke betraf.
    """
    ordner = bridge_dir(profile_id)
    hin = _lies(
        ordner / FPM_TO_BUDGETMANAGER,
        "FPM → BudgetManager",
        {"budgetmanager.import.v1"},
    )
    zurueck = _lies(
        ordner / BUDGETMANAGER_TO_FPM, "BudgetManager → FPM", _EXPENSE_SCHEMAS
    )
    ziele = _lies(
        ordner / BUDGETMANAGER_SAVINGS_GOALS,
        "Sparziele → FPM",
        _SAVINGS_GOAL_SCHEMAS,
    )
    return BridgeSummary(
        fpm_records=hin.eintraege,
        fpm_total=hin.summe,
        currencies=hin.waehrungen,
        invalid_lines=hin.ungueltige_zeilen,
        source_path=hin.pfad,
        fpm_nach_budgetmanager=hin,
        budgetmanager_nach_fpm=zurueck,
        sparziele=ziele,
    )
