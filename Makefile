.DEFAULT_GOAL := help
COMPOSE := docker compose

help: ## Liệt kê lệnh
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: ## Cài dependency Python + web, tạo .env
	uv sync --all-packages --all-extras  # extra `rag` (fastembed BM25) cần cho worker chạy bằng uv
	cd apps/web && npx -y pnpm@10 install
	@test -f .env || cp .env.example .env

infra: ## Chỉ Redis + Qdrant (để chạy service bằng uv/pnpm)
	$(COMPOSE) up -d redis qdrant

ingest-local: ## Nạp knowledge base bằng uv (idempotent)
	uv run --env-file .env python -m ai_service.rag.ingest --path data/knowledge

worker: ## AI worker bằng uv (Ctrl+C để dừng)
	uv run --env-file .env --package ai-service python -m ai_service.main

gateway: ## Gateway bằng uv, auto-reload, cổng 8080
	uv run --env-file .env --package gateway uvicorn gateway.main:app --reload --port 8080

web: ## Web dev server, cổng 3000
	cd apps/web && npx -y pnpm@10 dev

up: ## Chạy toàn bộ stack
	$(COMPOSE) up -d --build

down: ## Dừng stack
	$(COMPOSE) down

reset: ## Dừng + xóa dữ liệu dev (.storage/)
	$(COMPOSE) down -v
	rm -rf .storage

logs: ## Theo dõi log gateway + worker
	$(COMPOSE) logs -f gateway ai-worker

ingest: ## Nạp knowledge base (idempotent)
	$(COMPOSE) run --rm ingest

scale: ## make scale n=4
	$(COMPOSE) up -d --scale ai-worker=$(n)

check-openai: ## Kiểm tra OPENAI_API_KEY + model trong config/models.yaml
	uv run --env-file .env python scripts/check_models.py --ping

test: ## Test không gọi LLM (nhanh, miễn phí): pytest + Vitest
	uv run pytest -m "not llm"
	cd apps/web && npx -y pnpm@10 test

test-llm: ## Test gọi OpenAI thật (cần OPENAI_API_KEY)
	uv run pytest -m llm

lint: ## ruff + mypy + import-linter + web
	uv run ruff check . && uv run ruff format --check .
	uv run mypy packages/shared/src apps/gateway/src apps/ai-service/src
	uv run lint-imports
	cd apps/web && npx -y pnpm@10 lint && npx -y pnpm@10 typecheck

fmt: ## Format code
	uv run ruff check --fix . && uv run ruff format .

gen-types: ## Pydantic contracts → apps/web/lib/types.gen.ts
	./scripts/gen-types.sh

smoke: ## Compose (OpenAI thật) → smoke.sh
	$(COMPOSE) up -d --build
	./scripts/smoke.sh

playwright: ## Playwright (cần stack đang chạy + OpenAI thật, dùng Chrome đã cài)
	cd apps/web && npx -y pnpm@10 e2e

eval: ## Eval độ chính xác ai-service trên golden set (OpenAI thật; ARGS="--only qa- --no-judge")
	uv run --env-file .env python -m evals.run_eval --thresholds evals/thresholds.yaml --report evals/reports/$$(date +%Y-%m-%dT%H-%M) $(ARGS)

eval-baseline: ## Chép report eval mới nhất thành evals/reports/baseline.json
	@latest=$$(ls -t evals/reports/20*.json | head -1) && cp "$$latest" evals/reports/baseline.json && echo "baseline ← $$latest"

.PHONY: help setup infra ingest-local worker gateway web playwright up down reset logs ingest scale check-openai test test-llm lint fmt gen-types smoke eval eval-baseline
