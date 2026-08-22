"""Pytest-Konfiguration.

Loop 31: Das Bruecken-Register gehoert nie in die echte Nutzerkonfiguration.
Ohne diese Weiche traegt jeder Test, der einen Profilordner anlegt, seine
tmp-Pfade in ~/.config/fpm-suite/bridges.json ein - Pfade, die es nach dem
Testlauf nicht mehr gibt.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _bruecken_register_isolieren(tmp_path_factory, monkeypatch):
    ziel = tmp_path_factory.mktemp("bridge-registry") / "bridges.json"
    monkeypatch.setenv("FPM_SUITE_BRIDGE_REGISTRY", str(ziel))
    yield
