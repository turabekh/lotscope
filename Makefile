COMPOSE := docker compose
BACKEND := backend
INFRA := db redis martin

.PHONY: help up up-app down logs dev sync migrate revision test test-unit test-integration lint fmt typecheck check ingest e2e

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start local infrastructure (db, redis, martin)
	$(COMPOSE) up -d $(INFRA)

up-app: ## Build and start the full stack including the api container
	$(COMPOSE) --profile app up -d --build

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail service logs
	$(COMPOSE) logs -f

dev: ## Run the api with autoreload
	cd $(BACKEND) && uv run uvicorn lotscope.api.app:app --reload --host 0.0.0.0 --port 8000

sync: ## Install backend dependencies
	cd $(BACKEND) && uv sync

migrate: ## Apply database migrations
	cd $(BACKEND) && uv run alembic upgrade head

revision: ## Create a migration (use: make revision m="message")
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

test: ## Run the full test suite (unit + integration; needs Docker)
	cd $(BACKEND) && uv run pytest

test-unit: ## Run unit tests only (no Docker)
	cd $(BACKEND) && uv run pytest -m "not integration"

test-integration: ## Run integration tests only (requires Docker)
	cd $(BACKEND) && uv run pytest -m integration

lint: ## Lint
	cd $(BACKEND) && uv run ruff check .

fmt: ## Format and autofix
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .

typecheck: ## Type-check
	cd $(BACKEND) && uv run mypy

check: lint typecheck test-unit ## Run lint, type-check, and unit tests (fast pre-commit gate)

ingest: ## Run data ingestion (all datasets, or: make ingest DATASETS="opa pwd")
	cd $(BACKEND) && uv run python -m lotscope.ingestion.cli $(DATASETS)

e2e: ## Run end-to-end tests (added with the frontend slice)
	@echo "e2e is not implemented yet (see CLAUDE.md build order step 10)" && exit 1
