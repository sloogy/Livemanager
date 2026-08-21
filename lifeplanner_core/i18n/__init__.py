"""Übersetzungen für die Host-Oberfläche.

Der LifePlanner war als einziges Programm der Suite einsprachig: Seine Texte
standen fest im Quelltext, während BudgetManager, FPM und FreizeitManager
längst Deutsch, Englisch und Französisch sprachen. Wer die Module auf
Französisch benutzte, sah den Rahmen darum weiterhin auf Deutsch.

Bewusst schlank gehalten. Der Host verwaltet keine Beträge und keine Datumsangaben,
darum gibt es hier weder Währungs- noch Regionslogik - nur Texte.

    from lifeplanner_core.i18n import t
    t("app.title")
    t("module.installed", name="BudgetManager")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

ORDNER = Path(__file__).resolve().parent
STANDARD = "de"
SPRACHEN: dict[str, str] = {"de": "Deutsch", "en": "English", "fr": "Français"}

_texte: dict[str, dict[str, str]] = {}
_aktuell = STANDARD


def _laden(sprache: str) -> dict[str, str]:
    """Flache Schlüssel-Text-Zuordnung einer Sprachdatei."""
    if sprache in _texte:
        return _texte[sprache]
    pfad = ORDNER / f"{sprache}.json"
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as fehler:
        # Eine fehlende oder kaputte Sprachdatei darf den Start nicht
        # verhindern - dann steht eben der Schlüssel da, und das Log sagt warum.
        _log.warning("Sprachdatei %s nicht lesbar: %s", pfad.name, fehler)
        roh = {}
    _texte[sprache] = {k: str(v) for k, v in _flach(roh)}
    return _texte[sprache]


def _flach(daten: object, praefix: str = ""):
    """Verschachteltes JSON zu ``bereich.schluessel``."""
    if isinstance(daten, dict):
        for schluessel, wert in daten.items():
            neu = f"{praefix}.{schluessel}" if praefix else str(schluessel)
            yield from _flach(wert, neu)
    else:
        yield praefix, daten


def sprache() -> str:
    return _aktuell


def setze_sprache(sprache: str) -> None:
    """Stellt die Sprache um; unbekannte Kürzel fallen auf Deutsch zurück."""
    global _aktuell
    _aktuell = sprache if sprache in SPRACHEN else STANDARD


def t(schluessel: str, **werte: object) -> str:
    """Übersetzter Text; fehlt er, gilt Deutsch, sonst der Schlüssel selbst.

    Ein fehlender Platzhalter macht den Text nicht unbrauchbar: Dann steht die
    Rohfassung da, statt dass ein KeyError die Oberfläche zerlegt.
    """
    text = _laden(_aktuell).get(schluessel)
    if text is None and _aktuell != STANDARD:
        text = _laden(STANDARD).get(schluessel)
    if text is None:
        _log.debug("Kein Text für %r", schluessel)
        return schluessel
    if not werte:
        return text
    try:
        return text.format(**werte)
    except (KeyError, IndexError, ValueError):
        _log.warning("Platzhalter passen nicht zu %r", schluessel)
        return text
