.DEFAULT_GOAL := help
COMPOSE := docker compose

help: ## Liệt kê lệnh
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: ## Cài dependency Python + web, tạo .env
	uv sync --all-packages
	cd apps/web && npx -y pnpm@10 install
	@test -f .env || cp .env.example .env

up: ## Chạy toàn bộ stack
	$(COMPOSE) up -d --build

down: ## Dừng stack
	$(COMPOSE) down

reset: ## Dừng + xóa volume
	$(COMPOSE) down -v

logs: ## Theo dõi log gateway + worker
	$(COMPOSE) logs -f gateway ai-worker

ingest: ## Nạp knowledge base (idempotent)
	$(COMPOSE) run --rm ingest

scale: ## make scale n=4
	$(COMPOSE) up -d --scale ai-worker=$(n)

test: ## Test không gọi LLM (nhanh, miễn phí)
	uv run pytest -m "not llm"

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

eval: ## Chạy golden set (OpenAI thật)
	uv run python -m evals.run_eval --thresholds evals/thresholds.yaml --report evals/reports/$$(date +%Y-%m-%dT%H-%M)

.PHONY: help setup up down reset logs ingest scale test test-llm lint fmt gen-types smoke eval
