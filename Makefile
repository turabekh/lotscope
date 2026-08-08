COMPOSE := docker compose
BACKEND := backend
FRONTEND := frontend
INFRA := db redis martin mailpit

.PHONY: help up up-app down logs dev dev-api sync migrate revision seed gold-set gold-set-select recompute-verdicts recompute-distress recompute-vacancy recompute-assemblage ingest-title14 load-phillycode derive-phillycode demo test-image test test-unit test-integration lint fmt typecheck check fmt-check ingest e2e e2e-seed e2e-install web-install web-dev web-build web-test web-lint web-typecheck docker-prune

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start local infrastructure (db, redis, martin)
	$(COMPOSE) up -d $(INFRA)

up-app: ## Build and start the full stack including the api container
	$(COMPOSE) --profile app up -d --build

down: ## Stop all services
	$(COMPOSE) down

docker-prune: ## Reclaim Docker disk safely (build cache + unused images; NEVER touches volumes)
	docker builder prune -f
	docker image prune -af

logs: ## Tail service logs
	$(COMPOSE) logs -f

dev: ## Run the api and the frontend dev server together
	$(MAKE) -j2 dev-api web-dev

dev-api: ## Run the api with autoreload
	cd $(BACKEND) && uv run uvicorn lotscope.api.app:app --reload --host 0.0.0.0 --port 8000

sync: ## Install backend dependencies
	cd $(BACKEND) && uv sync

migrate: ## Apply database migrations
	cd $(BACKEND) && uv run alembic upgrade head

revision: ## Create a migration (use: make revision m="message")
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

seed: ## Seed reference data (zoning standards for every market)
	cd $(BACKEND) && uv run python -m lotscope.zoning.seed

gold-set-select: ## Select the gold-set parcels for review (writes the gitignored real set)
	cd $(BACKEND) && uv run python -m lotscope.goldset.select_cli $(ARGS)

gold-set: ## Evaluate the Philadelphia gold set against current verdicts (FILE=... to override)
	cd $(BACKEND) && uv run python -m lotscope.goldset.cli $(FILE)

recompute-verdicts: ## Recompute the Parcel Verdict for every parcel
	cd $(BACKEND) && uv run python -m lotscope.verdict.jobs

graduate-hbg-zoning: ## Lift the Harrisburg provisional zoning cap (run ONLY after reviewer sign-off): make graduate-hbg-zoning CONFIRM=--confirm
	cd $(BACKEND) && uv run python scripts/graduate_hbg_zoning.py $(CONFIRM)

recompute-distress: ## Recompute the motivated-seller distress index for every parcel
	cd $(BACKEND) && uv run python -m lotscope.distress.jobs

recompute-vacancy: ## Recompute the vacancy-confidence cross-check for every vacant parcel
	cd $(BACKEND) && uv run python -m lotscope.vacancy.jobs

recompute-assemblage: ## Recompute assemblage Top Plays for every vacant parcel
	cd $(BACKEND) && uv run python -m lotscope.assemblage.jobs

vapid-keys: ## Generate a VAPID keypair for web push (copy into .env)
	cd $(BACKEND) && uv run python -m lotscope.notifications.vapid_keys

ingest-title14: ## Embed the Title 14 corpus (use: make ingest-title14 FILE=data/title14/sections.jsonl)
	cd $(BACKEND) && uv run python -m lotscope.ai.corpus $(FILE)

load-phillycode: ## Load the parsed Philadelphia Code (QA-gated) into code_provision
	cd $(BACKEND) && uv run python -m lotscope.provisions.cli $(ARGS)

derive-phillycode: ## Derive and embed document rows from code_provision (prose only; tables are Slice 2b)
	cd $(BACKEND) && uv run python -m lotscope.ai.phillycode_cli $(ARGS)

demo: ## Load a small synthetic demo dataset and compute its verdicts (local preview)
	$(COMPOSE) exec -T db psql -U lotscope -d lotscope < $(BACKEND)/data/demo/demo.sql
	$(MAKE) recompute-verdicts

test-image: ## Build the PostGIS + pgvector image used by integration tests
	docker build -t lotscope/postgres:test docker/postgres

test: test-image ## Run the full test suite (unit + integration; needs Docker)
	cd $(BACKEND) && uv run pytest

test-unit: ## Run unit tests only (no Docker)
	cd $(BACKEND) && uv run pytest -m "not integration"

test-integration: test-image ## Run integration tests only (requires Docker)
	cd $(BACKEND) && uv run pytest -m integration

lint: ## Lint (backend + frontend)
	cd $(BACKEND) && uv run ruff check .
	cd $(FRONTEND) && pnpm lint

fmt: ## Format and autofix (backend + frontend)
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .
	cd $(FRONTEND) && pnpm format

fmt-check: ## Check formatting without writing (backend + frontend); mirrors CI
	cd $(BACKEND) && uv run ruff format --check .
	cd $(FRONTEND) && pnpm format:check

typecheck: ## Type-check (backend + frontend)
	cd $(BACKEND) && uv run mypy
	cd $(FRONTEND) && pnpm typecheck

check: lint fmt-check typecheck test-unit web-test ## Run lint, format, type-check, and unit tests (fast pre-commit gate)

web-install: ## Install frontend dependencies
	cd $(FRONTEND) && pnpm install

web-dev: ## Run the frontend dev server
	cd $(FRONTEND) && pnpm dev

web-build: ## Build the frontend
	cd $(FRONTEND) && pnpm build

web-test: ## Run frontend unit tests
	cd $(FRONTEND) && pnpm test

web-lint: ## Lint the frontend
	cd $(FRONTEND) && pnpm lint

web-typecheck: ## Type-check the frontend
	cd $(FRONTEND) && pnpm typecheck

ingest: ## Run data ingestion (all datasets, or: make ingest DATASETS="opa pwd")
	cd $(BACKEND) && uv run python -m lotscope.ingestion.cli $(DATASETS)

e2e: ## Run end-to-end tests (needs make up and a running api: make dev-api)
	cd $(BACKEND) && uv run python scripts/seed_e2e.py
	cd $(FRONTEND) && pnpm exec playwright test

e2e-seed: ## Load the end-to-end fixture parcels and compute their verdicts
	cd $(BACKEND) && uv run python scripts/seed_e2e.py

e2e-install: ## Install the Chromium build Playwright drives
	cd $(FRONTEND) && pnpm exec playwright install --with-deps chromium
