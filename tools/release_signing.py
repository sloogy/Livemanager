from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseSigning:
    private_key_b64: str
    public_key_b64: str

    @property
    def unsigned(self) -> bool:
        return not self.private_key_b64


def resolve_release_signing(*, allow_unsigned: bool) -> ReleaseSigning:
    """Resolve an explicitly signed or explicitly unsigned release mode."""
    private_key = os.environ.get("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", "").strip()
    public_key = os.environ.get("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", "").strip()

    if allow_unsigned:
        if private_key or public_key:
            raise RuntimeError(
                "--allow-unsigned darf nicht zusammen mit LIFEPLANNER_UPDATE_PRIVATE_KEY_B64 "
                "oder LIFEPLANNER_UPDATE_PUBLIC_KEY_B64 verwendet werden."
            )
        return ReleaseSigning(private_key_b64="", public_key_b64="")

    if not private_key or not public_key:
        raise RuntimeError(
            "Für einen signierten Release fehlen LIFEPLANNER_UPDATE_PRIVATE_KEY_B64 und/oder "
            "LIFEPLANNER_UPDATE_PUBLIC_KEY_B64. Für den bewussten Erst-Release ohne Signatur "
            "muss --allow-unsigned ausdrücklich gesetzt werden."
        )

    from lifeplanner_core.updater.signing import public_key_base64

    try:
        derived_public_key = public_key_base64(private_key)
    except Exception as exc:
        raise RuntimeError(f"Der private Release-Schlüssel ist ungültig: {exc}") from exc
    if derived_public_key != public_key:
        raise RuntimeError("Release-Private-Key und Release-Public-Key gehören nicht zusammen.")
    return ReleaseSigning(private_key_b64=private_key, public_key_b64=public_key)


def resolve_package_private_key(*, allow_unsigned: bool, private_key_b64: str) -> str:
    private_key = str(private_key_b64).strip()
    if allow_unsigned:
        if private_key:
            raise RuntimeError("--allow-unsigned darf nicht zusammen mit einem Private-Key verwendet werden.")
        return ""
    if not private_key:
        raise RuntimeError(
            "Private-Key fehlt. Ein unsigniertes .lpmodule muss ausdrücklich mit "
            "--allow-unsigned gebaut werden."
        )
    return private_key
