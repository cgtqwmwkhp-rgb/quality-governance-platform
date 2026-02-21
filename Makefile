.PHONY: dev test lint migrate build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
dev: ## Start development servers
	docker-compose up -d db redis
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
	cd frontend && npm run dev &

dev-full: ## Start all services including Celery
	docker-compose up -d

# Testing
test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	python -m pytest tests/unit/ -x --tb=short -q

test-integration: ## Run integration tests (requires DB)
	python -m pytest tests/integration/ --tb=short -q

test-frontend: ## Run frontend tests
	cd frontend && npx vitest run

test-e2e: ## Run E2E tests
	cd frontend && npx playwright test

test-coverage: ## Run tests with coverage
	python -m pytest tests/unit/ --cov=src --cov-report=html --cov-report=term
	cd frontend && npx vitest run --coverage

# Code Quality
lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Run Python linters
	black --check src/ tests/
	isort --check-only src/ tests/
	flake8 src/ tests/
	mypy src/

lint-frontend: ## Run TypeScript/JS linters
	cd frontend && npx tsc --noEmit

format: ## Auto-format all code
	black src/ tests/
	isort src/ tests/
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css,json}"

# Database
migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## Rollback last migration
	alembic downgrade -1

# Build
build: ## Build production images
	docker build -t quality-governance-platform .
	cd frontend && npm run build

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist htmlcov .coverage
