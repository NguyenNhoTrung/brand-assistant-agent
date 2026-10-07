"""Đếm token theo tokenizer của OpenAI (cl100k_base — cùng họ với text-embedding-3-*)."""

from functools import cache

import tiktoken


@cache
def _encoding() -> tiktoken.Encoding | None:
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # lần đầu cần tải file BPE — offline thì ước lượng
        return None


def count_tokens(text: str) -> int:
    enc = _encoding()
    return len(enc.encode(text)) if enc else max(1, len(text) // 4)


def tail_tokens(text: str, n: int) -> str:
    """n token cuối của text — dùng làm overlap giữa hai mảnh."""
    enc = _encoding()
    if enc is None:
        return text[-n * 4 :]
    ids = enc.encode(text)
    return enc.decode(ids[-n:]) if len(ids) > n else text


def split_tokens(text: str, n: int) -> list[str]:
    """Cắt cứng theo token — chỉ dùng khi một đoạn văn đơn lẻ dài hơn giới hạn."""
    enc = _encoding()
    if enc is None:
        return [text[i : i + n * 4] for i in range(0, len(text), n * 4)]
    ids = enc.encode(text)
    return [enc.decode(ids[i : i + n]) for i in range(0, len(ids), n)]
