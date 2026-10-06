FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY packages ./packages
COPY apps/ai-service ./apps/ai-service
COPY apps/gateway/pyproject.toml ./apps/gateway/pyproject.toml
RUN uv sync --frozen --no-dev --package ai-service --extra rag
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/app/.fastembed
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding('Qdrant/bm25', cache_dir='/app/.fastembed')" \
    && chown -R 1000:1000 /app/.fastembed
USER 1000:1000
CMD ["python", "-m", "ai_service.main"]
