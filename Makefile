.DEFAULT_GOAL := help

.PHONY: help install dev test migrate migration seed db-up docker-up docker-down docker-logs clean

help: ## Show this help message
	@echo "Family Expense Manager - Backend Make Commands"
	@echo "================================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install/sync all dependencies into virtual environment using uv
	uv sync

dev: ## Start FastAPI development server with auto-reload
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run test suite using pytest
	uv run pytest -v

migrate: ## Apply latest database migrations using Alembic
	uv run alembic upgrade head

migration: ## Generate a new migration revision (Usage: make migration name="add_users")
	@if [ -z "$(name)" ]; then echo "Error: Please specify migration name (e.g. make migration name=\"create_users\")"; exit 1; fi
	uv run alembic revision --autogenerate -m "$(name)"

seed: ## Safely and idempotently seed default system categories
	uv run python -m app.scripts.seed_categories

db-up: ## Start only PostgreSQL database container in the background
	docker compose up -d db

docker-up: ## Start both API and PostgreSQL in background using Docker Compose
	docker compose up -d

docker-build: ## Build and start containers with Docker Compose
	docker compose up --build

docker-down: ## Stop all Docker Compose containers
	docker compose down

docker-logs: ## Tail logs from Docker Compose containers
	docker compose logs -f api

clean: ## Remove temporary cache and bytecode files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -exec rm -f {} +
