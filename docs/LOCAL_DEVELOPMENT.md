# Local Development Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- Git

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/cgtqwmwkhp-rgb/quality-governance-platform.git
cd quality-governance-platform
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env  # Edit with your local settings

# Start infrastructure services
docker-compose up -d db redis

# Run database migrations
alembic upgrade head

# Seed initial data
python -m src.domain.services.ims_seed_service

# Start the API server
uvicorn src.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:5173

### 4. Background Workers (Optional)

```bash
# Start Celery worker
celery -A src.infrastructure.tasks.celery_app worker --loglevel=info

# Start Celery beat (scheduled tasks)
celery -A src.infrastructure.tasks.celery_app beat --loglevel=info

# Start Flower (task monitoring)
celery -A src.infrastructure.tasks.celery_app flower --port=5555
```

### 5. Full Stack with Docker

```bash
docker-compose up --build
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key | (required) |
| `ENVIRONMENT` | `development` / `staging` / `production` | `development` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/1` |

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/ --cov=src --cov-report=term

# Integration tests
pytest tests/integration/

# With coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Code Quality

```bash
# Format code
black src/ tests/ --line-length 120
isort src/ tests/ --profile black

# Lint
flake8 src/ tests/
mypy src/

# Frontend
cd frontend && npx tsc --noEmit
```

## Troubleshooting

### Database connection errors
Ensure PostgreSQL is running: `docker-compose ps db`

### Redis connection errors
Ensure Redis is running: `docker-compose ps redis`

### Migration conflicts
```bash
alembic heads  # Check for multiple heads
alembic merge heads  # Merge if needed
```
