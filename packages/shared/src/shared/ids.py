import os
import time
import uuid


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def uuid7() -> uuid.UUID:
    """UUIDv7 (RFC 9562): 48 bit timestamp ms + 74 bit ngẫu nhiên — sắp xếp được theo thời gian."""
    ts = now_ms() & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = rand >> 68 & 0xFFF
    rand_b = rand & ((1 << 62) - 1)
    value = ts << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b
    return uuid.UUID(int=value)
