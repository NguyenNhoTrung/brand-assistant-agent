"""CLI debug retrieval: `python -m ai_service.rag "câu hỏi" [--doc-type product] [-k 5] [--en "english query"]`."""

import argparse
import asyncio

from redis.asyncio import Redis

from ai_service.llm.client import embeddings
from ai_service.rag.qdrant_store import make_client
from ai_service.rag.retriever import RetrievalQuery, Retriever
from ai_service.settings import settings


async def _run(args: argparse.Namespace) -> None:
    redis = Redis.from_url(settings.redis_url)
    qdrant = make_client()
    try:
        retriever = Retriever(qdrant, embeddings(redis), settings.qdrant_collection)
        q = RetrievalQuery(text=args.question, text_en=args.en, doc_types=args.doc_type or None)
        res = await retriever.hybrid_search(q, k=args.k)
    finally:
        await qdrant.close()
        await redis.aclose()
    print(f"max_cosine = {res.max_cosine:.3f}")
    for i, c in enumerate(res.chunks, start=1):
        print(f"{i:>2}. {c.score:.4f}  {c.source_path:<40} [{c.doc_type}] v{c.version} {c.effective_date}")
        print(f"      § {c.section[:100]}")
        if args.show:
            print("      " + c.content[:300].replace("\n", "\n      "))


def main() -> None:
    p = argparse.ArgumentParser(description="Thử hybrid search trên Qdrant")
    p.add_argument("question")
    p.add_argument("--doc-type", action="append", help="lọc theo doc_type (lặp lại được)")
    p.add_argument("--en", help="câu tiếng Anh cho nhánh BM25 (mặc định = câu gốc)")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--show", action="store_true", help="in đoạn đầu nội dung chunk")
    args = p.parse_args()
    settings.require_openai_key()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
