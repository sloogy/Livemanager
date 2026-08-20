from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lifeplanner_core.updater.package_builder import build_component_package
from tools.release_signing import resolve_package_private_key


def main() -> int:
    parser = argparse.ArgumentParser(description="Ein installierbares LifePlanner-.lpmodule-Paket bauen")
    parser.add_argument("module_dir", type=Path, help="Ordner mit module.json und Modul-Payload")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--requires-host", default=">=0.5.0")
    parser.add_argument("--platform", action="append", default=[], help="z. B. windows-x86_64 oder linux-x86_64")
    parser.add_argument("--private-key", default=os.environ.get("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", ""))
    parser.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="Baut bewusst ohne Signatur; nur für den ersten Release und manuell bestätigte lokale Installation.",
    )
    args = parser.parse_args()

    try:
        private_key = resolve_package_private_key(
            allow_unsigned=args.allow_unsigned,
            private_key_b64=args.private_key,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    module_dir = args.module_dir.resolve()
    manifest_path = module_dir / "module.json"
    if not manifest_path.is_file():
        raise SystemExit(f"module.json fehlt: {manifest_path}")
    info = json.loads(manifest_path.read_text(encoding="utf-8"))
    module_id = str(info.get("id", "")).strip()
    version = str(info.get("version", "")).strip()
    if not module_id or not version:
        raise SystemExit("module.json benötigt id und version")
    output = args.output or ROOT / "release" / "module-packages" / f"{module_id}_{version}.lpmodule"
    build_component_package(
        payload=module_dir,
        component_id=module_id,
        name=str(info.get("name", module_id)),
        version=version,
        kind="module",
        output=output,
        requires_host=args.requires_host,
        description=str(info.get("description", "")),
        platforms=args.platform,
        private_key_b64=private_key,
    )
    print(output)
    if not private_key:
        print("WARNUNG: Paket ist ausdrücklich nicht signiert; LifePlanner verlangt lokale Vertrauensbestätigung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
