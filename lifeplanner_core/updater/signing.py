from __future__ import annotations

import base64
import binascii
import os
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

PUBLIC_KEY_FILENAME = "lifeplanner_update_public_key.b64"


class UpdateSignatureError(ValueError):
    pass


def _decode(value: str | bytes, expected: int, label: str) -> bytes:
    raw = value.encode("ascii") if isinstance(value, str) else bytes(value)
    try:
        decoded = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UpdateSignatureError(f"{label} ist kein gültiges Base64") from exc
    if len(decoded) != expected:
        raise UpdateSignatureError(f"{label} muss {expected} Bytes enthalten")
    return decoded


def public_key_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "resources" / PUBLIC_KEY_FILENAME)
    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend(
        [
            executable_dir / "resources" / PUBLIC_KEY_FILENAME,
            executable_dir / "_internal" / "resources" / PUBLIC_KEY_FILENAME,
            Path(__file__).resolve().parents[1] / "resources" / PUBLIC_KEY_FILENAME,
        ]
    )
    seen: set[Path] = set()
    result: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)


def load_public_key() -> Ed25519PublicKey:
    env = os.environ.get("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", "").strip()
    if env:
        return Ed25519PublicKey.from_public_bytes(_decode(env, 32, "Update-Public-Key"))
    for path in public_key_candidates():
        if path.is_file():
            return Ed25519PublicKey.from_public_bytes(_decode(path.read_bytes(), 32, str(path)))
    raise UpdateSignatureError(
        "Kein vertrauenswürdiger LifePlanner-Update-Public-Key gefunden. "
        "Remote-Updates werden aus Sicherheitsgründen abgelehnt."
    )


def verify_manifest_signature(manifest_bytes: bytes, signature_bytes: bytes) -> None:
    signature = _decode(signature_bytes, 64, "Manifest-Signatur")
    try:
        load_public_key().verify(signature, manifest_bytes)
    except InvalidSignature as exc:
        raise UpdateSignatureError("Manifest-Signatur ist ungültig") from exc


def private_key_from_base64(value: str | bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_decode(value, 32, "Update-Private-Key"))


def sign_manifest(manifest_bytes: bytes, private_key_b64: str) -> bytes:
    return base64.b64encode(private_key_from_base64(private_key_b64).sign(manifest_bytes)) + b"\n"


def public_key_base64(private_key_b64: str) -> str:
    key = private_key_from_base64(private_key_b64)
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")
