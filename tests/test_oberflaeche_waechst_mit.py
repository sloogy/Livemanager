"""Die Oberflaeche waechst mit der eingestellten Schriftgroesse.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen. Feste
Pixelwerte im Stylesheet setzen sich sonst ueber die Profilschrift hinweg: Wer
die Schrift zur besseren Lesbarkeit hochstellt, bekaeme groesseren Text in
unveraendert engen Schaltflaechen.
"""

from __future__ import annotations

import re

import pytest

from lifeplanner_core.theme import ThemeCatalog, build_stylesheet


@pytest.fixture(scope="module")
def profil():
    katalog = ThemeCatalog()
    return katalog.resolve(katalog.names()[0])


def _stylesheet(profil, schriftgroesse: int) -> str:
    profil.data["schriftgroesse"] = schriftgroesse
    return build_stylesheet(profil)


def _groessen(css: str, eigenschaft: str) -> list[int]:
    return [int(x) for x in re.findall(rf"{eigenschaft}:\s*(\d+)px", css)]


@pytest.mark.parametrize("eigenschaft", ["font-size", "min-height", "border-radius"])
def test_die_masse_wachsen_mit_der_schrift(profil, eigenschaft):
    klein = _groessen(_stylesheet(profil, 8), eigenschaft)
    gross = _groessen(_stylesheet(profil, 16), eigenschaft)
    assert klein and len(klein) == len(gross), f"{eigenschaft} nicht vergleichbar"
    assert sum(gross) > sum(klein) * 1.3, (
        f"{eigenschaft} waechst kaum mit: {sum(klein)} -> {sum(gross)}"
    )


def test_die_radien_folgen_der_vorlage(profil):
    """Abgestuft wie im BudgetManager, der Design-Vorlage der Suite."""
    radien = set(_groessen(_stylesheet(profil, 10), "border-radius"))
    assert {6, 8}.issubset(radien), sorted(radien)
