.PHONY: dev test lint build docker lockfile clean help pr-ready start-branch pr-template

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start backend dev server
	uvicorn src.main:app --reload --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

install: ## Install all dependencies
	pip install -r requirements-dev.txt
	cd frontend && npm ci

test: ## Run all backend tests
	pytest tests/ -x --tb=short

test-unit: ## Run unit tests only
	pytest tests/unit/ -x --tb=short

test-integration: ## Run integration tests only
	pytest tests/integration/ -x --tb=short

test-frontend: ## Run frontend tests
	cd frontend && npx vitest run

lint: ## Run all linters
	black --check src/ tests/
	isort --check-only --settings-path pyproject.toml src/ tests/
	flake8 src/ tests/
	cd frontend && npx eslint src/ --max-warnings 0

lint-fix: ## Auto-fix linting issues
	black src/ tests/
	isort --settings-path pyproject.toml src/ tests/

pr-ready: ## Run local PR preflight checks
	./scripts/governance/pr-ready.sh

start-branch: ## Create a new branch from origin/main (usage: make start-branch BRANCH=fix/my-change)
	@if [ -z "$(BRANCH)" ]; then echo "Usage: make start-branch BRANCH=fix/my-change"; exit 1; fi
	./scripts/governance/start-branch.sh "$(BRANCH)"

pr-template: ## Show the CLI-safe PR body template path
	@echo "Use: gh pr create --body-file scripts/governance/pr_body_template.md"

build: ## Build frontend for production
	cd frontend && npm run build

docker: ## Build Docker image
	docker build -t qgp-backend:local .

docker-up: ## Start all services with Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

lockfile: ## Generate requirements.lock (requires Python 3.11+)
	./scripts/generate_lockfile.sh

migrate: ## Run database migrations
	alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

clean: ## Remove build artifacts
	rm -rf frontend/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
