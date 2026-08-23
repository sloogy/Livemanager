"""Die Host-Oberflaeche spricht Deutsch, Englisch und Franzoesisch.

Warum es das braucht: Der LifePlanner war als einziges Programm der Suite
einsprachig - seine Texte standen fest im Quelltext, waehrend BudgetManager,
FPM und FreizeitManager laengst drei Sprachen sprachen. Wer die Module auf
Franzoesisch benutzte, sah den Rahmen darum weiterhin auf Deutsch.

Geprueft wird zweierlei: dass keine Sprache Luecken hat, und dass in der
Oberflaeche keine neuen festen Texte auftauchen.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from lifeplanner_core.i18n import ORDNER, SPRACHEN, STANDARD, setze_sprache, t

WURZEL = Path(__file__).resolve().parents[1]
UI = WURZEL / "lifeplanner_core" / "ui"


def _flach(daten, praefix=""):
    if isinstance(daten, dict):
        for schluessel, wert in daten.items():
            neu = f"{praefix}.{schluessel}" if praefix else schluessel
            yield from _flach(wert, neu)
    else:
        yield praefix, daten


def _schluessel(sprache: str) -> dict[str, str]:
    pfad = ORDNER / f"{sprache}.json"
    return dict(_flach(json.loads(pfad.read_text(encoding="utf-8"))))


# ── Die Sprachdateien ───────────────────────────────────────────────────────

@pytest.mark.parametrize("sprache", sorted(SPRACHEN))
def test_jede_sprache_hat_dieselben_schluessel(sprache):
    deutsch = set(_schluessel(STANDARD))
    andere = set(_schluessel(sprache))
    assert not (deutsch - andere), f"{sprache}: fehlt {sorted(deutsch - andere)}"
    assert not (andere - deutsch), f"{sprache}: zuviel {sorted(andere - deutsch)}"


@pytest.mark.parametrize("sprache", sorted(SPRACHEN))
def test_kein_text_ist_leer(sprache):
    leer = [k for k, v in _schluessel(sprache).items() if not str(v).strip()]
    assert not leer, f"{sprache}: {leer}"


def test_die_uebersetzungen_sind_nicht_bloss_kopiert():
    """Eine Sprachdatei, die den deutschen Text durchreicht, waere unbemerkt
    wertlos. Ein paar Eigennamen duerfen gleich bleiben."""
    deutsch = _schluessel(STANDARD)
    for sprache in ("en", "fr"):
        andere = _schluessel(sprache)
        gleich = [k for k, v in andere.items() if v == deutsch[k]]
        anteil = len(gleich) / len(deutsch)
        assert anteil < 0.15, f"{sprache}: {anteil:.0%} unveraendert - {gleich[:5]}"


@pytest.mark.parametrize("sprache", sorted(SPRACHEN))
def test_die_platzhalter_stimmen_ueberein(sprache):
    """Ein fehlender Platzhalter faellt sonst erst zur Laufzeit auf."""
    muster = re.compile(r"\{(\w+)\}")
    deutsch = _schluessel(STANDARD)
    for schluessel, text in _schluessel(sprache).items():
        assert set(muster.findall(text)) == set(muster.findall(deutsch[schluessel])), (
            f"{sprache}: {schluessel}"
        )


# ── Die Oberflaeche ─────────────────────────────────────────────────────────

SICHTBAR_CALL = {"QLabel", "QPushButton", "QGroupBox", "QCheckBox", "QRadioButton",
                 "QListWidgetItem", "QAction", "QToolButton"}
SICHTBAR_METHODE = {"setText", "setWindowTitle", "setTitle", "setToolTip",
                    "setPlaceholderText", "addTab", "addRow", "information",
                    "warning", "critical", "question", "setStatusTip"}
LOGGER = {"_log", "log", "logger", "logging"}
# Kein Text, sondern Technik: Objektnamen, Formate, Platzhalter-URLs.
UNVERDAECHTIG = re.compile(r"^(https?://|[a-z_]+$|[A-Za-z]+[A-Z]\w*$|\W*$)")


def test_kein_fester_deutscher_text_mehr_in_der_oberflaeche():
    fundstellen = []
    for pfad in sorted(UI.glob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            f = knoten.func
            if isinstance(f, ast.Attribute):
                if isinstance(f.value, ast.Name) and f.value.id in LOGGER:
                    continue
                name = f.attr
            elif isinstance(f, ast.Name):
                name = f.id
            else:
                continue
            if name not in SICHTBAR_CALL and name not in SICHTBAR_METHODE:
                continue
            for arg in knoten.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    continue
                text = arg.value.strip()
                if len(text) < 4 or UNVERDAECHTIG.match(text):
                    continue
                if not any(c.isalpha() for c in text):
                    continue
                fundstellen.append(f"{pfad.name}:{arg.lineno}: {text[:50]!r}")
    assert not fundstellen, "fester Text statt t(...):\n" + "\n".join(fundstellen)


# ── Das Umschalten ──────────────────────────────────────────────────────────

def test_die_sprache_laesst_sich_umschalten():
    try:
        setze_sprache("fr")
        assert t("darstellung.uebernehmen") == "Appliquer"
        setze_sprache("en")
        assert t("darstellung.uebernehmen") == "Apply"
    finally:
        setze_sprache(STANDARD)


def test_ein_unbekanntes_kuerzel_faellt_auf_deutsch_zurueck():
    try:
        setze_sprache("kl")
        assert t("darstellung.uebernehmen") == "Übernehmen"
    finally:
        setze_sprache(STANDARD)


def test_ein_unbekannter_schluessel_zerlegt_nichts():
    """Er soll auffallen, aber die Oberflaeche nicht zum Absturz bringen."""
    assert t("gibt.es.nicht") == "gibt.es.nicht"


# ── Der gefrorene Build ─────────────────────────────────────────────────────

def _spec_datas() -> list[tuple[str, str]]:
    """Die ``datas``-Liste aus LifePlanner.spec, wirklich ausgewertet.

    Eine Textsuche wuerde die Zeile finden und nicht ihr Ergebnis. Der Kopf der
    Spec bis ``Analysis(`` kommt ohne PyInstaller-Globals aus - ausser
    ``SPECPATH``, das hier gesetzt wird.
    """
    spec = (WURZEL / "LifePlanner.spec").read_text(encoding="utf-8")
    kopf = spec.split("a = Analysis(", 1)[0]
    raum: dict[str, object] = {"SPECPATH": str(WURZEL)}
    exec(compile(kopf, "LifePlanner.spec", "exec"), raum)
    return list(raum["datas"])  # type: ignore[arg-type]


@pytest.mark.parametrize("sprache", sorted(SPRACHEN))
def test_der_gefrorene_build_bringt_jede_sprachdatei_mit(sprache):
    """Sie fehlten - und der Loader zeigte still den Schluessel statt des Textes.

    In der portablen 0.6.1 war damit die ganze Oberflaeche unbeschriftet, ohne
    dass etwas abstuerzte. Geprueft wird das Ziel mit: Liegt die Datei woanders
    als neben ``lifeplanner_core/i18n/__init__.py``, findet der Loader sie nicht.
    """
    ziel = "lifeplanner_core/i18n"
    dabei = [
        quelle
        for quelle, ordner in _spec_datas()
        if ordner == ziel and Path(quelle).name == f"{sprache}.json"
    ]
    assert dabei, f"{sprache}.json fehlt in den datas von LifePlanner.spec"
    assert Path(dabei[0]).is_file()
