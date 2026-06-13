.PHONY: help setup ingest build-index refresh lab dash deploy deploy-logs test lint fmt

COMPOSE = docker compose -f deploy/docker-compose.yml

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Create venv and install all dependencies
	uv sync --all-extras

refresh:  ## Ingest all sources and rebuild every index (the cron target)
	uv run python -m vantage.pipeline.refresh

ingest:  ## Alias for refresh (kept for clarity)
	uv run python -m vantage.pipeline.refresh

build-index:  ## Rebuild indices from already-ingested prices (no fetch)
	uv run python -m vantage.pipeline.refresh --no-prices

lab:  ## Launch JupyterLab for notebook exploration
	uv run jupyter lab

dash:  ## Run the terminal dashboard locally (http://localhost:8501)
	uv run streamlit run src/vantage/app/dashboard.py

deploy:  ## Build and start web + scheduler via Docker Compose (reads deploy/.env)
	$(COMPOSE) up -d --build

deploy-logs:  ## Tail logs from the deployed services
	$(COMPOSE) logs -f

test:  ## Run the test suite (offline; live tests skipped)
	uv run pytest

lint:  ## Lint with ruff
	uv run ruff check .

fmt:  ## Format with ruff
	uv run ruff format .
