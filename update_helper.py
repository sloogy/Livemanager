from __future__ import annotations

import argparse
import json
from pathlib import Path

from lifeplanner_core.updater.apply_plan import apply_plan, restart


def main() -> int:
    parser = argparse.ArgumentParser(description="Externer LifePlanner-Update-Helfer")
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    plan: dict = {}
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        apply_plan(plan_path)
        restart([str(value) for value in plan.get("restart_command", [])])
        return 0
    except Exception:
        # Nach einem fehlgeschlagenen, automatisch zurückgerollten Update wird
        # die bisherige Version neu geöffnet. Sie zeigt last_result.json an.
        if plan:
            restart([str(value) for value in plan.get("restart_command", [])])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
