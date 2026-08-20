from __future__ import annotations

import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption


def main() -> int:
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    print("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64=" + base64.b64encode(private_raw).decode("ascii"))
    print("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64=" + base64.b64encode(public_raw).decode("ascii"))
    print("\nDen privaten Schlüssel ausschließlich als geschütztes GitHub-Secret speichern.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
