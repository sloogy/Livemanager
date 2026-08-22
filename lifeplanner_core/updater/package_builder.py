from __future__ import annotations

import json
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from .io import tree_sha256
from .signing import sign_manifest


def build_component_package(
    *,
    payload: Path,
    component_id: str,
    name: str,
    version: str,
    kind: str,
    output: Path,
    requires_host: str = "",
    description: str = "",
    platforms: Iterable[str] = (),
    private_key_b64: str = "",
) -> Path:
    """Build a deterministic LifePlanner component or ``.lpmodule`` package."""

    payload = payload.resolve()
    if not payload.is_dir():
        raise ValueError(f"Payload-Ordner fehlt: {payload}")
    if kind not in {"core", "module"}:
        raise ValueError(f"Ungültiger Komponententyp: {kind}")
    metadata = {
        "schema": "lifeplanner.component.v1",
        "id": component_id,
        "name": name,
        "version": version,
        "kind": kind,
        "requires_host": requires_host,
        "description": description,
        "platforms": sorted({str(value).strip().lower() for value in platforms if str(value).strip()}),
        "payload_sha256": tree_sha256(payload),
        "created_at": datetime.now(UTC).isoformat(),
    }
    metadata_bytes = (json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("component.json", metadata_bytes)
        if private_key_b64:
            archive.writestr("component.json.sig", sign_manifest(metadata_bytes, private_key_b64))
        for path in sorted(payload.rglob("*"), key=lambda value: value.as_posix()):
            if path.is_file():
                archive.write(path, Path("payload") / path.relative_to(payload))
    return output
