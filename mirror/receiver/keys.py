"""Strict Ed25519 public key validation."""


def public_key(value):
    import base64
    import struct

    parts = value.strip().split()
    if len(parts) != 2 or parts[0] != "ssh-ed25519":
        raise ValueError("Cola uma chave pública Ed25519, sem opções ou comentários.")
    try:
        blob = base64.b64decode(parts[1], validate=True)
        if (
            len(blob) != 51
            or blob[:4] != struct.pack(">I", 11)
            or blob[4:15] != b"ssh-ed25519"
            or blob[15:19] != struct.pack(">I", 32)
        ):
            raise ValueError
    except Exception:
        raise ValueError("A chave pública Ed25519 não é válida.") from None
    return " ".join(parts)
