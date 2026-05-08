.PHONY: dev worker worker-llm worker-parsing flower migrate migrate-down \
        test test-unit test-integration test-e2e lint format typecheck \
        seed clean docker-up docker-down install install-dev setup

# ─── Local dev ─────────────────────────────────────────────────────────────
dev:            ## Run FastAPI dev server with hot-reload
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

worker:         ## Start Celery worker (all queues)
	celery -A app.workers.celery_app worker --loglevel=info \
	       -Q parsing,embeddings,llm,default -c 4

worker-parsing: ## Start worker for parsing queue only
	celery -A app.workers.celery_app worker --loglevel=info -Q parsing -c 4

worker-llm:     ## Start worker for LLM queue only
	celery -A app.workers.celery_app worker --loglevel=info -Q llm -c 2

worker-beat:    ## Start Celery Beat scheduler
	celery -A app.workers.celery_app beat --loglevel=info

flower:         ## Open Celery Flower monitoring UI (port 5555)
	celery -A app.workers.celery_app flower --port=5555

# ─── Database ──────────────────────────────────────────────────────────────
migrate:        ## Run Alembic migrations (upgrade head)
	alembic upgrade head

migrate-down:   ## Roll back last Alembic migration
	alembic downgrade -1

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add table")
	alembic revision --autogenerate -m "$(MSG)"

# ─── Testing ───────────────────────────────────────────────────────────────
test:           ## Run full test suite with coverage
	pytest --cov=app --cov-report=term-missing --cov-report=html -v

test-unit:      ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

test-e2e:       ## Run e2e tests only
	pytest tests/e2e/ -v

# ─── Code Quality ──────────────────────────────────────────────────────────
lint:           ## Run ruff linter + black check
	ruff check app/ tests/
	black --check app/ tests/

format:         ## Auto-format code with ruff + black
	ruff check --fix app/ tests/
	black app/ tests/

typecheck:      ## Run mypy static type checking
	mypy app/ --ignore-missing-imports

# ─── Dependencies ──────────────────────────────────────────────────────────
install:        ## Install production dependencies
	pip install -r requirements.txt
	python -m spacy download en_core_web_sm

install-dev:    ## Install dev + production dependencies
	pip install -r requirements-dev.txt
	python -m spacy download en_core_web_sm

# ─── Docker Compose ────────────────────────────────────────────────────────
docker-up:      ## Start all services via Docker Compose
	docker compose -f infra/docker-compose.yml up -d

docker-down:    ## Stop all services
	docker compose -f infra/docker-compose.yml down

docker-logs:    ## Tail logs from all services
	docker compose -f infra/docker-compose.yml logs -f

docker-build:   ## Build the backend Docker image
	docker compose -f infra/docker-compose.yml build backend

# ─── Setup ─────────────────────────────────────────────────────────────────
setup:          ## Full local dev setup (install + docker + migrate + seed)
	$(MAKE) install-dev
	$(MAKE) docker-up
	sleep 5
	$(MAKE) migrate
	python scripts/seed_data.py

seed:           ## Seed dev database with sample data
	python scripts/seed_data.py

clean:          ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
