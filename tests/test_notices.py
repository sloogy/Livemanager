"""Der Host sammelt die Meldungen der Module ein.

Bis Loop 47 zeigte das Dashboard nur, ob die Module laufen und wie viele
Zeilen in den Brueckendateien stehen. Ein ueberzogenes Budget sah nur, wer
den BudgetManager oeffnete - obwohl der Host das Fenster ist, das ohnehin
offen steht.

Die Tests halten vor allem eines fest: **Der Host bewertet nichts.** Er liest
die Dringlichkeit, die das Modul geschickt hat. Alles andere waere eine
zweite Fachlogik neben der ersten.
"""

from __future__ import annotations

import json

import pytest

from lifeplanner_core.notices import (
    DRINGLICHKEITEN,
    GROESSENGRENZE,
    HOECHSTZAHL,
    MANIFEST_SCHEMA,
    NOTICE_SCHEMA,
    STANDARD_DRINGLICHKEIT,
    _lies_datei,
)


def _datei(tmp_path, name: str, zeilen: list[dict], *, kopf: dict | None = None):
    pfad = tmp_path / name
    inhalt = []
    if kopf is not None:
        inhalt.append(json.dumps(kopf, ensure_ascii=False))
    inhalt.extend(json.dumps(z, ensure_ascii=False) for z in zeilen)
    pfad.write_text("\n".join(inhalt) + "\n", encoding="utf-8")
    return pfad


def _meldung(**felder) -> dict:
    basis = {
        "schema": NOTICE_SCHEMA,
        "id": "abc123",
        "urgency": "warnung",
        "headline": "Miete: 92 % verbraucht",
        "detail": "08/2026",
        "area": "budget",
    }
    basis.update(felder)
    return basis


def test_meldung_wird_vollstaendig_gelesen(tmp_path) -> None:
    pfad = _datei(
        tmp_path,
        "budgetmanager_notices.jsonl",
        [_meldung()],
        kopf={"schema": MANIFEST_SCHEMA, "module": "BudgetManager"},
    )
    meldungen, ungueltig = _lies_datei(pfad)
    assert ungueltig == 0
    (m,) = meldungen
    assert m.modul == "BudgetManager"
    assert m.dringlichkeit == "warnung"
    assert m.ueberschrift == "Miete: 92 % verbraucht"
    assert m.zusatz == "08/2026"


def test_ohne_kopfzeile_traegt_der_dateiname_den_absender(tmp_path) -> None:
    """Eine grobe Zuordnung ist besser als eine Meldung ohne Absender."""
    pfad = _datei(tmp_path, "fpm_notices.jsonl", [_meldung()])
    meldungen, _ = _lies_datei(pfad)
    assert meldungen[0].modul == "fpm"


def test_unbekannte_dringlichkeit_wird_nicht_verworfen(tmp_path) -> None:
    """Eine neue Stufe heisst neueres Modul, nicht kaputte Datei.

    Verwerfen hiesse, dass ein aelterer Host die Meldung eines neueren
    Moduls verschluckt - genau dann, wenn sie am wichtigsten ist.
    """
    pfad = _datei(tmp_path, "x_notices.jsonl", [_meldung(urgency="dringend")])
    meldungen, ungueltig = _lies_datei(pfad)
    assert ungueltig == 0
    assert meldungen[0].dringlichkeit == STANDARD_DRINGLICHKEIT


def test_meldung_ohne_ueberschrift_zaehlt_als_ungueltig(tmp_path) -> None:
    """Eine leere Zeile im Dashboard sagt weniger als gar keine."""
    pfad = _datei(tmp_path, "x_notices.jsonl", [_meldung(headline="   ")])
    meldungen, ungueltig = _lies_datei(pfad)
    assert meldungen == []
    assert ungueltig == 1


def test_fremdes_schema_wird_nicht_angezeigt(tmp_path) -> None:
    """Die Brueckendateien liegen im selben Ordner."""
    pfad = _datei(
        tmp_path,
        "x_notices.jsonl",
        [{"schema": "fpm.import.v1", "amount": 42.0, "category": "Tinte"}],
    )
    meldungen, ungueltig = _lies_datei(pfad)
    assert meldungen == []
    assert ungueltig == 1


def test_kaputte_zeile_stoppt_die_datei_nicht(tmp_path) -> None:
    pfad = tmp_path / "x_notices.jsonl"
    pfad.write_text(
        json.dumps(_meldung(id="eins")) + "\n"
        "{kaputt\n" + json.dumps(_meldung(id="zwei")) + "\n",
        encoding="utf-8",
    )
    meldungen, ungueltig = _lies_datei(pfad)
    assert [m.kennung for m in meldungen] == ["eins", "zwei"]
    assert ungueltig == 1


def test_zu_grosse_datei_wird_nicht_gelesen(tmp_path) -> None:
    """Ein Modul mit einem Schreibfehler darf den Host nicht anhalten."""
    pfad = tmp_path / "x_notices.jsonl"
    pfad.write_text("x" * (GROESSENGRENZE + 1), encoding="utf-8")
    meldungen, ungueltig = _lies_datei(pfad)
    assert meldungen == []
    assert ungueltig == 1


def test_fehlende_datei_ist_kein_fehler(tmp_path) -> None:
    meldungen, ungueltig = _lies_datei(tmp_path / "gibtsnicht_notices.jsonl")
    assert meldungen == []
    assert ungueltig == 1


def test_dringlichkeiten_stimmen_mit_der_schreibseite_ueberein() -> None:
    """Dieselbe Reihenfolge wie im BudgetManager.

    Weichen sie ab, sortiert der Host anders, als das Modul gemeint hat.
    """
    assert DRINGLICHKEITEN == ("info", "warnung", "kritisch")
    assert STANDARD_DRINGLICHKEIT in DRINGLICHKEITEN


def test_der_deckel_ist_gesetzt() -> None:
    """Ein Dashboard, das man scrollen muss, wird nicht gelesen."""
    assert 0 < HOECHSTZAHL <= 100


@pytest.mark.parametrize("stufe", DRINGLICHKEITEN)
def test_jede_dringlichkeit_wird_uebernommen(tmp_path, stufe) -> None:
    pfad = _datei(tmp_path, "x_notices.jsonl", [_meldung(urgency=stufe)])
    meldungen, _ = _lies_datei(pfad)
    assert meldungen[0].dringlichkeit == stufe
