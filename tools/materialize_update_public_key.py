from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="LifePlanner Update-Public-Key für den Build materialisieren")
    parser.add_argument("--out", type=Path, default=ROOT / "lifeplanner_core/resources/lifeplanner_update_public_key.b64")
    parser.add_argument("--key", default=os.environ.get("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", ""))
    args = parser.parse_args()
    value = str(args.key).strip()
    if not value:
        raise SystemExit("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64 fehlt")
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise SystemExit(f"Ungültiger Base64-Public-Key: {exc}") from exc
    if len(decoded) != 32:
        raise SystemExit("Ed25519-Public-Key muss 32 Bytes enthalten")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(value + "\n", encoding="ascii")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
