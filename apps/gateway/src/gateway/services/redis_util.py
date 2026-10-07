def s(v: bytes | str) -> str:
    return v.decode() if isinstance(v, bytes) else v


def decode_hash(h: dict) -> dict[str, str]:
    return {s(k): s(v) for k, v in h.items()}
