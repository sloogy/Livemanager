"""Der Host erkennt beide Richtungen der Bruecke.

Warum es das braucht: Der LifePlanner las lange nur
``fpm_to_budgetmanager.jsonl``. Schrieb BudgetManager seine Sparziele nicht
heraus - und das tat er nur auf ausdruecklichen Knopfdruck -, war das hier
nicht zu sehen. Die Anzeige meldete unauffaellig einen Stand, der nur die
halbe Bruecke betraf.

Die Proben stammen wortgetreu aus den beiden Modulen; die Gegenstuecke heissen
FPM/tests/test_budgetmanager_bridge_contract.py und
Budgetmanager/tests/test_fpm_bridge_contract.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lifeplanner_core.bridge import (
    BUDGETMANAGER_SAVINGS_GOALS,
    BUDGETMANAGER_TO_FPM,
    FPM_TO_BUDGETMANAGER,
    summarize_fpm_outbox,
)

PROFIL = "testprofil-bruecke"


@pytest.fixture()
def bruecke(tmp_path, monkeypatch) -> Path:
    """Ein eigener Datenwurzelordner - kein Zugriff auf das echte Profil.

    Die Variable heisst LIFEPLANNER_DATA_DIR; mit einem falschen Namen legt
    der Test seine Dateien still im Quellbaum an und sieht dort die Reste des
    vorigen Laufs.
    """
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path))
    from lifeplanner_core.paths import bridge_dir

    return bridge_dir(PROFIL)


def _schreib(ordner: Path, name: str, *eintraege: dict) -> None:
    (ordner / name).write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in eintraege) + "\n",
        encoding="utf-8",
    )


# Wortgetreu aus FPM/logic/budget_export_service.py.
FPM_AUSGABE = {
    "schema": "budgetmanager.import.v1",
    "operation": "upsert",
    "external_id": "fpm:expense:5",
    "source": "FPM",
    "date": "2026-07-04",
    "amount": 320.0,
    "currency": "CHF",
    "category_path": "Hobby/Füller",
    "description": "Pilot Custom 823",
}

# Wortgetreu aus Budgetmanager/model/lifeplanner_import_service.py.
BM_AUSGABE = {
    "schema": "fpm.import.v1",
    "operation": "upsert",
    "external_id": "budgetmanager:tracking:77",
    "source": "BudgetManager",
    "date": "2026-07-04",
    "amount": 42.0,
    "currency": "CHF",
    "category_path": "Füller",
    "description": "Pilot Custom",
}
BM_SPARZIEL = {
    "schema": "fpm.savings-goal.v1",
    "external_id": "budgetmanager:savings-goal:1",
    "source": "BudgetManager",
    "item_type": "savings_goal",
    "label": "Pilot Custom 823",
    "goal_name": "Pilot Custom 823",
    "status": "sparend",
    "target_amount": 300.0,
    "current_amount": 120.0,
    "remaining_amount": 180.0,
    "progress_percent": 40.0,
    "currency": "CHF",
    "deadline": "2026-09-01",
    "category": "Füller",
    "notes": "",
}


# ── Alle drei Dateien werden gelesen ────────────────────────────────────────

def test_leere_bruecke_meldet_dreimal_noch_nichts_geschrieben(bruecke):
    """Fehlende Datei heisst: das Programm hat noch nichts abgelegt."""
    befund = summarize_fpm_outbox(PROFIL)
    assert len(befund.dateien) == 3
    assert all(not d.vorhanden for d in befund.dateien)
    assert befund.gesamt_eintraege == 0


def test_die_fpm_richtung_wird_gezaehlt(bruecke):
    _schreib(
        bruecke,
        FPM_TO_BUDGETMANAGER,
        {"schema": "budgetmanager.import.manifest.v1"},
        FPM_AUSGABE,
    )
    befund = summarize_fpm_outbox(PROFIL)
    assert befund.fpm_nach_budgetmanager.eintraege == 1
    assert befund.fpm_nach_budgetmanager.summe == 320.0
    # Die alten Felder bleiben, damit bestehende Aufrufer weiterlaufen.
    assert befund.fpm_records == 1
    assert befund.fpm_total == 320.0


def test_die_gegenrichtung_wird_gezaehlt(bruecke):
    """Die wurde vorher gar nicht angesehen."""
    _schreib(
        bruecke,
        BUDGETMANAGER_TO_FPM,
        {"schema": "fpm.import.manifest.v1"},
        BM_AUSGABE,
    )
    befund = summarize_fpm_outbox(PROFIL)
    assert befund.budgetmanager_nach_fpm.eintraege == 1
    assert befund.budgetmanager_nach_fpm.summe == 42.0


def test_die_sparziele_werden_gezaehlt(bruecke):
    """Der Fall, der den Nutzer gestoert hat."""
    _schreib(
        bruecke,
        BUDGETMANAGER_SAVINGS_GOALS,
        {"schema": "fpm.savings-goals.manifest.v1"},
        BM_SPARZIEL,
    )
    befund = summarize_fpm_outbox(PROFIL)
    assert befund.sparziele.vorhanden
    assert befund.sparziele.eintraege == 1
    # Sparziele tragen keinen Betrag, sondern ein Ziel.
    assert befund.sparziele.summe == 300.0


def test_die_aeltere_unterstrich_form_gilt_weiter(bruecke):
    _schreib(
        bruecke,
        BUDGETMANAGER_SAVINGS_GOALS,
        dict(BM_SPARZIEL, schema="fpm.savings_goal.v1"),
    )
    assert summarize_fpm_outbox(PROFIL).sparziele.eintraege == 1


def test_alles_zusammen_wird_aufaddiert(bruecke):
    _schreib(bruecke, FPM_TO_BUDGETMANAGER, FPM_AUSGABE)
    _schreib(bruecke, BUDGETMANAGER_TO_FPM, BM_AUSGABE)
    _schreib(bruecke, BUDGETMANAGER_SAVINGS_GOALS, BM_SPARZIEL)
    assert summarize_fpm_outbox(PROFIL).gesamt_eintraege == 3


# ── Fehlt, leer oder fehlerhaft - der Unterschied zaehlt ────────────────────

def test_eine_leere_datei_ist_etwas_anderes_als_eine_fehlende(bruecke):
    """Sonst waere nicht zu erkennen, ob das Modul nichts geschrieben hat oder
    nichts zu schreiben hatte."""
    (bruecke / BUDGETMANAGER_SAVINGS_GOALS).write_text("", encoding="utf-8")
    befund = summarize_fpm_outbox(PROFIL)
    assert befund.sparziele.vorhanden
    assert befund.sparziele.leer
    assert not befund.fpm_nach_budgetmanager.vorhanden
    assert not befund.fpm_nach_budgetmanager.leer


def test_kaputte_zeilen_werden_gemeldet_statt_verschluckt(bruecke):
    (bruecke / BUDGETMANAGER_TO_FPM).write_text(
        json.dumps(BM_AUSGABE) + "\nkein json\n" + json.dumps({"schema": "fremd.v1"}) + "\n",
        encoding="utf-8",
    )
    befund = summarize_fpm_outbox(PROFIL)
    assert befund.budgetmanager_nach_fpm.eintraege == 1
    assert befund.budgetmanager_nach_fpm.ungueltige_zeilen == 2


def test_das_manifest_zaehlt_nirgends_als_eintrag(bruecke):
    for name, manifest in (
        (FPM_TO_BUDGETMANAGER, "budgetmanager.import.manifest.v1"),
        (BUDGETMANAGER_TO_FPM, "fpm.import.manifest.v1"),
        (BUDGETMANAGER_SAVINGS_GOALS, "fpm.savings-goals.manifest.v1"),
    ):
        _schreib(bruecke, name, {"schema": manifest})
    befund = summarize_fpm_outbox(PROFIL)
    assert befund.gesamt_eintraege == 0
    assert all(d.ungueltige_zeilen == 0 for d in befund.dateien)
