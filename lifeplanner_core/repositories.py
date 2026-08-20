from __future__ import annotations

import sys
from dataclasses import dataclass

CORE_REPOSITORY = "sloogy/Livemanager"
BUDGETMANAGER_REPOSITORY = "sloogy/Budgetmanager"
FPM_REPOSITORY = "sloogy/FPM"

CORE_LATEST_MANIFEST_URL = (
    f"https://github.com/{CORE_REPOSITORY}/releases/latest/download/lifeplanner-latest.json"
)


@dataclass(frozen=True)
class TrustedModuleRepository:
    module_id: str
    name: str
    repository: str
    description: str
    # Älteste Version, die im Host tragfähig ist. Ältere Releases werden im
    # Katalog nicht angeboten, auch wenn sie ein passendes Asset mitbringen.
    minimum_version: str = ""


TRUSTED_MODULE_REPOSITORIES = (
    TrustedModuleRepository(
        module_id="budgetmanager",
        name="BudgetManager",
        repository=BUDGETMANAGER_REPOSITORY,
        description="Budget, Buchungen, Forecasts, Sparziele und Monatsabschluss.",
        # Vor 2.2.62 brach die Übersicht unter Fedora/Wayland in CompactChart ab.
        minimum_version="2.2.62",
    ),
    TrustedModuleRepository(
        module_id="fpm",
        name="FPM - Fountain Pen Manager",
        repository=FPM_REPOSITORY,
        description="Füller, Tinten, Federn, Papier, Rotation und Sammlungswissen.",
        minimum_version="1.0.0",
    ),
)


def current_platform_asset_suffix() -> str:
    if sys.platform.startswith("win"):
        return "Windows_x86_64"
    if sys.platform.startswith("linux"):
        return "Linux_x86_64"
    raise RuntimeError(f"Nicht unterstützte LifePlanner-Plattform: {sys.platform}")


def module_asset_pattern(module_id: str) -> str:
    safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in module_id)
    suffix = current_platform_asset_suffix()
    return rf"{safe_id}_(?P<version>[0-9][0-9A-Za-z._-]*)_{suffix}\.lpmodule"
