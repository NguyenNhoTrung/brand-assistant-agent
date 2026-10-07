FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY packages ./packages
COPY apps/gateway ./apps/gateway
COPY apps/ai-service/pyproject.toml ./apps/ai-service/pyproject.toml
RUN uv sync --frozen --no-dev --package gateway
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER 1000:1000
EXPOSE 8080
# --no-access-log: middleware đã log mỗi request dạng JSON (request_id, user_id, job_id)
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
