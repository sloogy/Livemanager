from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .manifest import ModuleManifest
from .paths import bridge_dir

# Legacy-Verträge der ersten beiden Module. Sie bleiben als Fallback erhalten,
# damit bereits installierte module.v1-Pakete ohne deklarative Bridge-Contracts
# weiterhin sichtbar sind.
FPM_TO_BUDGETMANAGER = "fpm_to_budgetmanager.jsonl"
BUDGETMANAGER_TO_FPM = "budgetmanager_to_fpm.jsonl"
BUDGETMANAGER_SAVINGS_GOALS = "budgetmanager_savings_goals.jsonl"

_MANIFEST_SCHEMAS = {
    "budgetmanager.import.manifest.v1",
    "fpm.import.manifest.v1",
    "fpm.savings-goals.manifest.v1",
    "fpm.savings_goals.manifest.v1",
    "freizeitmanager.focus.manifest.v1",
}

_SAVINGS_GOAL_SCHEMAS = {"fpm.savings-goal.v1", "fpm.savings_goal.v1"}
_EXPENSE_SCHEMAS = {"fpm.import.v1", "fpm.expense.v1"}
_LEGACY_FILES = {
    FPM_TO_BUDGETMANAGER,
    BUDGETMANAGER_TO_FPM,
    BUDGETMANAGER_SAVINGS_GOALS,
}


@dataclass(frozen=True)
class DateiBefund:
    """Was in einer deklarierten Brückendatei steht."""

    name: str
    pfad: Path
    vorhanden: bool
    eintraege: int
    summe: float
    waehrungen: tuple[str, ...]
    ungueltige_zeilen: int
    module_id: str = ""
    direction: str = "publish"

    @property
    def leer(self) -> bool:
        return self.vorhanden and self.eintraege == 0


@dataclass(frozen=True)
class BridgeSummary:
    """Der Zustand der Brücke insgesamt.

    Die alten Felder bleiben API-kompatibel. ``weitere`` enthält alle
    Publish-Outboxen, die installierte module.v2-Manifeste zusätzlich
    deklarieren (z. B. den FreizeitManager-Fokus).
    """

    fpm_records: int
    fpm_total: float
    currencies: tuple[str, ...]
    invalid_lines: int
    source_path: Path
    fpm_nach_budgetmanager: DateiBefund | None = None
    budgetmanager_nach_fpm: DateiBefund | None = None
    sparziele: DateiBefund | None = None
    weitere: tuple[DateiBefund, ...] = ()

    @property
    def dateien(self) -> tuple[DateiBefund, ...]:
        feste = tuple(
            befund
            for befund in (
                self.fpm_nach_budgetmanager,
                self.budgetmanager_nach_fpm,
                self.sparziele,
            )
            if befund is not None
        )
        return feste + self.weitere

    @property
    def gesamt_eintraege(self) -> int:
        return sum(befund.eintraege for befund in self.dateien)


def _lies(
    pfad: Path,
    name: str,
    gueltige_schemas: set[str],
    *,
    module_id: str = "",
    direction: str = "publish",
) -> DateiBefund:
    """Zählt gültige Einträge einer JSONL-Datei, ohne Rohdaten zu übernehmen."""
    if not pfad.is_file():
        return DateiBefund(
            name, pfad, False, 0, 0.0, (), 0, module_id=module_id, direction=direction
        )

    eintraege = 0
    summe = 0.0
    ungueltig = 0
    waehrungen: set[str] = set()
    try:
        zeilen = pfad.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return DateiBefund(
            name, pfad, True, 0, 0.0, (), 1, module_id=module_id, direction=direction
        )

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
        if schema in _MANIFEST_SCHEMAS:
            continue
        if schema not in gueltige_schemas:
            ungueltig += 1
            continue
        eintraege += 1
        betrag = eintrag.get("amount")
        if betrag is None:
            betrag = eintrag.get("target_amount")
        if betrag is not None:
            try:
                summe += float(betrag)
            except (TypeError, ValueError):
                ungueltig += 1
        waehrung = str(eintrag.get("currency") or "").strip()
        if waehrung:
            waehrungen.add(waehrung)

    return DateiBefund(
        name,
        pfad,
        True,
        eintraege,
        round(summe, 2),
        tuple(sorted(waehrungen)),
        ungueltig,
        module_id=module_id,
        direction=direction,
    )


def summarize_declared_bridges(
    profile_id: str, manifests: Iterable[ModuleManifest]
) -> tuple[DateiBefund, ...]:
    """Liest die von module.v2-Manifests deklarierten Publish-Outboxen.

    Der Core kennt dadurch keine Fachdaten oder neuen Dateinamen. Ein Modul
    meldet lediglich Datei und erlaubte Schemas; der Host zählt Statusdaten.
    Subscribe-Verträge werden hier bewusst nicht als Quelle angezeigt.
    """
    root = bridge_dir(profile_id)
    findings: list[DateiBefund] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for manifest in manifests:
        for contract in manifest.bridge_contracts:
            if contract.direction != "publish":
                continue
            key = (contract.filename, contract.schemas)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                _lies(
                    root / contract.filename,
                    contract.name,
                    set(contract.schemas),
                    module_id=manifest.module_id,
                    direction=contract.direction,
                )
            )
    return tuple(findings)


def summarize_fpm_outbox(profile_id: str) -> BridgeSummary:
    """Legacy-Brücke plus alle zusätzlich deklarierten Modul-Outboxen."""
    ordner = bridge_dir(profile_id)
    hin = _lies(
        ordner / FPM_TO_BUDGETMANAGER,
        "FPM → BudgetManager",
        {"budgetmanager.import.v1"},
        module_id="fpm",
    )
    zurueck = _lies(
        ordner / BUDGETMANAGER_TO_FPM,
        "BudgetManager → FPM",
        _EXPENSE_SCHEMAS,
        module_id="budgetmanager",
    )
    ziele = _lies(
        ordner / BUDGETMANAGER_SAVINGS_GOALS,
        "Sparziele → FPM",
        _SAVINGS_GOAL_SCHEMAS,
        module_id="budgetmanager",
    )

    # Später Import vermeidet einen Zyklus manifest -> paths -> bridge.
    from .plugin_loader import discover_modules

    declared = summarize_declared_bridges(profile_id, discover_modules().modules)
    weitere = tuple(item for item in declared if item.pfad.name not in _LEGACY_FILES)
    return BridgeSummary(
        fpm_records=hin.eintraege,
        fpm_total=hin.summe,
        currencies=hin.waehrungen,
        invalid_lines=hin.ungueltige_zeilen,
        source_path=hin.pfad,
        fpm_nach_budgetmanager=hin,
        budgetmanager_nach_fpm=zurueck,
        sparziele=ziele,
        weitere=weitere,
    )
