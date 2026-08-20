from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat

from lifeplanner_core.updater.manifest import UpdateManifestError, compare_manifest, parse_manifest, platform_key
from lifeplanner_core.updater.signing import verify_manifest_signature


def _manifest() -> dict:
    return {
        "schema": "lifeplanner.update.v1",
        "channel": "stable",
        "generated_at": "2026-07-30T12:00:00+00:00",
        "components": {
            "lifeplanner.core": {
                "id": "lifeplanner.core",
                "name": "LifePlanner Core",
                "version": "0.3.0",
                "kind": "core",
                "assets": {
                    platform_key(): {
                        "url": "https://example.org/core.zip",
                        "sha256": "a" * 64,
                        "size": 123,
                        "type": "component-zip",
                    }
                },
            },
            "fpm": {
                "id": "fpm",
                "name": "FPM",
                "version": "0.3.5",
                "kind": "module",
                "requires_host": ">=0.3.0",
                "assets": {
                    platform_key(): {
                        "url": "https://example.org/fpm.zip",
                        "sha256": "b" * 64,
                        "size": 456,
                        "type": "component-zip",
                    }
                },
            },
        },
    }


def test_manifest_compares_core_and_modules() -> None:
    manifest = parse_manifest(_manifest())
    statuses = compare_manifest(
        manifest,
        {"lifeplanner.core": "0.2.0", "fpm": "0.3.4"},
        host_version="0.2.0",
    )
    by_id = {status.component_id: status for status in statuses}
    assert by_id["lifeplanner.core"].update_available
    assert by_id["fpm"].update_available
    assert by_id["fpm"].compatible


def test_manifest_rejects_bad_hash_and_unknown_schema() -> None:
    raw = _manifest()
    raw["components"]["fpm"]["assets"][platform_key()]["sha256"] = "bad"
    with pytest.raises(UpdateManifestError):
        parse_manifest(raw)
    raw = _manifest()
    raw["schema"] = "other"
    with pytest.raises(UpdateManifestError):
        parse_manifest(raw)


def test_detached_ed25519_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", base64.b64encode(public_raw).decode("ascii"))
    payload = json.dumps(_manifest(), sort_keys=True).encode("utf-8")
    signature = base64.b64encode(private.sign(payload)) + b"\n"
    verify_manifest_signature(payload, signature)
    with pytest.raises(Exception):
        verify_manifest_signature(payload + b"x", signature)
