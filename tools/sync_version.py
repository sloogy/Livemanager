#!/usr/bin/env python3
"""Synchronisiert APP_VERSION in die Release-Dateien des LifePlanners.

Quelle: ``lifeplanner_core.APP_VERSION``.

Warum es diese Datei gibt: Die Version stand bisher an sechs Stellen und musste
bei jedem Release von Hand nachgezogen werden - in der Workflow-Datei allein
neunmal. Vergass man eine, schlug der Paketest fehl oder, schlimmer, der
Workflow suchte nach einer Datei, die der Build unter anderem Namen abgelegt
hatte.

Die Versionshistorie in ``CHANGELOG.md`` wird bewusst nicht angefasst.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lifeplanner_core import APP_VERSION

# Dateien, die immer die aktuelle Version beschreiben. CHANGELOG.md fehlt hier
# absichtlich - dort steht der Verlauf.
VERSION_BEARING = (
    "README.md",
    "installer/LifePlanner.iss",
    "dependencies/modules.lock.json",
    "dependencies/installer-module-sources.example.json",
    ".github/workflows/release.yml",
)


def _pattern(series: str) -> re.Pattern[str]:
    """Versionen derselben Reihe - auch mitten im Wort und vor einer Endung.

    Der Blick nach vorn wehrt laengere Versionen ab, der nach hinten verhindert,
    dass aus ``1.0.5.8`` etwas wird. ``python-version: "3.12"`` bleibt unberuehrt,
    weil dort die dritte Stelle fehlt.
    """
    return re.compile(rf"(?<![\d.]){re.escape(series)}\.\d+(?!\.?\d)")


def sync(check: bool, source_version: str | None = None) -> int:
    series = (source_version or APP_VERSION).rsplit(".", 1)[0]
    pattern = _pattern(series)
    stale: list[str] = []

    for rel in VERSION_BEARING:
        path = ROOT / rel
        if not path.is_file():
            print(f"  fehlt: {rel}", file=sys.stderr)
            continue
        src = path.read_text(encoding="utf-8")
        new = pattern.sub(APP_VERSION, src)
        if new == src:
            continue
        if check:
            stale.append(rel)
            continue
        path.write_text(new, encoding="utf-8")

    if check:
        if stale:
            print(f"VERSION MISMATCH (Quelle lifeplanner_core = {APP_VERSION}):")
            for rel in stale:
                print(f"  - {rel} ist nicht synchron")
            return 1
        print(f"Alle Versionsdateien synchron: {APP_VERSION}")
        return 0
    print(f"Versionen synchronisiert auf {APP_VERSION}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="nur pruefen, nichts schreiben")
    parser.add_argument("--from", dest="source", default=None,
                        help="Reihe der bisherigen Version, falls sie sich mit "
                             "diesem Release aendert (z. B. 0.5.9 bei 0.6.0)")
    args = parser.parse_args(argv)
    return sync(args.check, args.source)


if __name__ == "__main__":
    raise SystemExit(main())
