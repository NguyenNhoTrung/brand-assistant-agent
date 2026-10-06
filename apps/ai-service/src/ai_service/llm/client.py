"""Điểm DUY NHẤT tạo model. Node chỉ gọi chat(alias) / structured(...) / embeddings()."""

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from ai_service.llm.config import ModelAlias, load_models
from ai_service.settings import settings


def _base(alias: ModelAlias, *, streaming: bool = False) -> BaseChatModel:
    c = load_models(settings.models_file)[alias]
    return ChatOpenAI(
        model=c.model,
        api_key=settings.require_openai_key(),
        timeout=c.timeout,
        max_tokens=c.max_tokens,  # type: ignore[call-arg]
        max_retries=2,
        streaming=streaming,
        stream_usage=True,
        metadata={"model_alias": alias},
    )


def chat(alias: ModelAlias, *, streaming: bool = False) -> Runnable:
    primary = _base(alias, streaming=streaming)
    fb = load_models(settings.models_file)[alias].fallback
    return primary.with_fallbacks([_base(fb, streaming=streaming)]) if fb else primary


# TODO(P0): structured(alias, schema) · embeddings() + CachedEmbeddings · tracing.JobTracer · pricing
