"""Kiểm tra OPENAI_API_KEY và các model trong config/models.yaml.

uv run --env-file .env python scripts/check_models.py           # liệt kê + đối chiếu
uv run --env-file .env python scripts/check_models.py --ping    # gọi thử mỗi model 1 lần (tốn vài token)
"""

import argparse
import os
import sys

import openai
import yaml

MODELS_FILE = "config/models.yaml"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ping", action="store_true", help="gọi thử mỗi model một lần")
    args = p.parse_args()

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print("✗ OPENAI_API_KEY trống — điền vào .env và chạy với `uv run --env-file .env ...`")
        return 1
    print(f"• Key: {key[:3]}…{key[-4:]} (dài {len(key)} ký tự)")

    client = openai.OpenAI(api_key=key)
    try:
        available = {m.id for m in client.models.list()}
    except openai.AuthenticationError as e:
        print(f"✗ Key không hợp lệ (401): {e.body.get('message') if isinstance(e.body, dict) else e}")
        return 1
    except openai.APIError as e:
        print(f"✗ OpenAI trả lỗi: {e}")
        return 1
    print(f"• Key dùng được, truy cập {len(available)} model\n")

    with open(MODELS_FILE) as f:
        cfg = yaml.safe_load(f)
    missing = 0
    for alias, c in cfg.items():
        ok = c["model"] in available
        missing += not ok
        status = "OK  " if ok else "MISS"
        line = f"{status} {alias:<13} {c['model']}"
        if ok and args.ping:
            line += "  " + ping(client, alias, c["model"])
        print(line)

    if missing:
        chat_models = sorted(m for m in available if m.startswith(("gpt-", "o")) and "embedding" not in m)
        print(f"\n{missing} model không có → sửa {MODELS_FILE}. Một số model chat khả dụng:")
        print("  " + ", ".join(chat_models[:30]))
        return 1
    return 0


def ping(client: openai.OpenAI, alias: str, model: str) -> str:
    try:
        if alias == "embed":
            r = client.embeddings.create(model=model, input="ping")
            return f"→ embed dim={len(r.data[0].embedding)}"
        r = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Reply with: pong"}], max_completion_tokens=200
        )
        return f"→ {(r.choices[0].message.content or '').strip()[:20]!r}"
    except openai.APIError as e:
        return f"→ lỗi: {e}"


if __name__ == "__main__":
    sys.exit(main())
