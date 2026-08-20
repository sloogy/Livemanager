from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import bridge_dir


@dataclass(frozen=True)
class BridgeSummary:
    fpm_records: int
    fpm_total: float
    currencies: tuple[str, ...]
    invalid_lines: int
    source_path: Path


def summarize_fpm_outbox(profile_id: str) -> BridgeSummary:
    path = bridge_dir(profile_id) / "fpm_to_budgetmanager.jsonl"
    if not path.is_file():
        return BridgeSummary(0, 0.0, (), 0, path)
    count = 0
    total = 0.0
    invalid = 0
    currencies: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            invalid += 1
            continue
        schema = obj.get("schema")
        if schema == "budgetmanager.import.manifest.v1":
            continue
        if schema != "budgetmanager.import.v1":
            invalid += 1
            continue
        count += 1
        try:
            total += float(obj.get("amount", 0) or 0)
        except (TypeError, ValueError):
            invalid += 1
        currencies.add(str(obj.get("currency") or "CHF"))
    return BridgeSummary(count, round(total, 2), tuple(sorted(currencies)), invalid, path)
