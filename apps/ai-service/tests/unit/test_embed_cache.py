import fakeredis
from langchain_core.embeddings import Embeddings

from ai_service.llm.embed_cache import CachedEmbeddings


class CountingEmbeddings(Embeddings):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t)), 0.5, -1.0] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


async def test_second_call_hits_cache_only_for_seen_texts() -> None:
    r = fakeredis.FakeAsyncRedis()
    inner = CountingEmbeddings()
    emb = CachedEmbeddings(inner, r, model="m")
    assert await emb.aembed_documents(["a", "bb"]) == [[1.0, 0.5, -1.0], [2.0, 0.5, -1.0]]
    assert await emb.aembed_documents(["bb", "ccc", "a"]) == [[2.0, 0.5, -1.0], [3.0, 0.5, -1.0], [1.0, 0.5, -1.0]]
    assert inner.calls == [["a", "bb"], ["ccc"]]
    assert (emb.hits, emb.misses) == (2, 3)
    assert await emb.aembed_query("a") == [1.0, 0.5, -1.0]
    keys = sorted(k.decode() for k in await r.keys("emb:m:*"))
    assert len(keys) == 3 and all(len(k.split(":")[2]) == 64 for k in keys)
    assert 0 < await r.ttl(keys[0]) <= 7 * 86400


async def test_empty_input() -> None:
    emb = CachedEmbeddings(CountingEmbeddings(), fakeredis.FakeAsyncRedis(), model="m")
    assert await emb.aembed_documents([]) == []
