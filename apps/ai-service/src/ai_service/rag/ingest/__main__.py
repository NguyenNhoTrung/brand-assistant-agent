"""`python -m ai_service.rag.ingest --path data/knowledge [--recreate]` — idempotent theo content_hash."""

import argparse
import asyncio
import sys
from pathlib import Path

from redis.asyncio import Redis

from ai_service.llm.client import embeddings
from ai_service.rag.ingest.manifest import Manifest
from ai_service.rag.ingest.pipeline import run_ingest
from ai_service.rag.qdrant_store import make_client
from ai_service.settings import settings


async def _run(path: Path, recreate: bool) -> int:
    redis = Redis.from_url(settings.redis_url)
    qdrant = make_client()
    try:
        report = await run_ingest(
            path,
            qdrant=qdrant,
            manifest=Manifest(redis),
            embedder=embeddings(redis),
            collection=settings.qdrant_collection,
            recreate=recreate,
        )
    finally:
        await qdrant.close()
        await redis.aclose()
    print(f"[ingest] {settings.qdrant_collection}: {report.summary()}")
    for p, err in report.rejected.items():
        print(f"[ingest] REJECTED {p}: {err}", file=sys.stderr)
    return 1 if report.rejected else 0


def main() -> None:
    p = argparse.ArgumentParser(description="Nạp knowledge base vào Qdrant")
    p.add_argument("--path", default="data/knowledge")
    p.add_argument("--recreate", action="store_true", help="xóa collection + kb:manifest rồi nạp lại toàn bộ")
    args = p.parse_args()
    settings.require_openai_key()  # embedding cần OpenAI — fail fast
    path = Path(args.path)
    if not path.is_dir():
        sys.exit(f"[ingest] không thấy thư mục {path}")
    sys.exit(asyncio.run(_run(path, args.recreate)))


if __name__ == "__main__":
    main()
