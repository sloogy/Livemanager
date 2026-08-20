from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import APP_VERSION
from .paths import app_dir, data_root, logs_dir
from .plugin_loader import discover_modules


def build_diagnostics() -> dict:
    result = discover_modules()
    return {
        "schema": "lifeplanner.diagnostics.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lifeplanner_version": APP_VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "app_dir": str(app_dir()),
        "data_root": str(data_root()),
        "modules": [
            {"id": m.module_id, "name": m.name, "version": m.version, "path": str(m.module_dir)}
            for m in result.modules
        ],
        "module_errors": list(result.errors),
    }


def write_diagnostics() -> Path:
    path = logs_dir() / "lifeplanner_diagnostics.json"
    path.write_text(json.dumps(build_diagnostics(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
