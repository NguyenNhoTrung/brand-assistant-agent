"""Điểm DUY NHẤT tạo model. Node chỉ gọi chat(alias) / structured(...) / embeddings()."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel

from ai_service.llm.config import ModelAlias, load_models
from ai_service.llm.embed_cache import CachedEmbeddings
from ai_service.settings import settings

if TYPE_CHECKING:  # agent import client → không được kéo redis vào lúc chạy (.importlinter)
    from redis.asyncio import Redis


def _base(alias: ModelAlias, *, streaming: bool = False) -> BaseChatModel:
    c = load_models(settings.models_file)[alias]
    return ChatOpenAI(
        model=c.model,
        api_key=settings.require_openai_key(),
        timeout=c.timeout,
        max_tokens=c.max_tokens,  # type: ignore[call-arg]
        max_retries=2,  # retry có backoff của OpenAI SDK — tầng retry LLM duy nhất
        streaming=streaming,
        stream_usage=True,
        metadata={"model_alias": alias},
    )


def _with_fallback(alias: ModelAlias, build: Callable[[ModelAlias], Runnable]) -> Runnable:
    primary = build(alias)
    fb = load_models(settings.models_file)[alias].fallback
    return primary.with_fallbacks([build(fb)]) if fb else primary  # một bước, không lồng


def chat(alias: ModelAlias, *, streaming: bool = False) -> Runnable:
    return _with_fallback(alias, lambda a: _base(a, streaming=streaming))


def structured(alias: ModelAlias, schema: type[BaseModel]) -> Runnable:
    return _with_fallback(alias, lambda a: _base(a).with_structured_output(schema, method="json_schema", strict=True))


def embeddings(redis: "Redis") -> CachedEmbeddings:
    """Embedding model `embed` bọc cache Redis — dùng chung cho ingest và query."""
    c = load_models(settings.models_file)["embed"]
    base = OpenAIEmbeddings(
        model=c.model,
        api_key=settings.require_openai_key(),
        dimensions=c.dims,
        timeout=c.timeout,
        max_retries=2,
    )
    return CachedEmbeddings(base, redis, model=c.model)


# TODO(P0): tracing.JobTracer · pricing
