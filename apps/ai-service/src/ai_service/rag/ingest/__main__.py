"""`python -m ai_service.rag.ingest --path /data/knowledge [--recreate]`

TODO(P0) theo §10: loader (frontmatter) → validator → chunker theo heading → embed (dense + BM25)
→ upsert Qdrant → kb:manifest. Idempotent theo content_hash.
"""

import argparse
from pathlib import Path

from ai_service.settings import settings


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--path", default="data/knowledge")
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args()
    settings.require_openai_key()  # embedding cần OpenAI
    files = sorted(Path(args.path).rglob("*.md"))
    print(f"[ingest] skeleton: tìm thấy {len(files)} file markdown, chưa nạp vào Qdrant")


if __name__ == "__main__":
    main()
