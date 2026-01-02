# Quality Governance Platform

Enterprise-grade Integrated Management System (IMS) for ISO compliance and quality governance.

## Overview

This platform provides a unified governance solution covering:

- **ISO 9001** - Quality Management
- **ISO 14001** - Environmental Management
- **ISO 27001** - Information Security Management
- **ISO 45001** - Occupational Health & Safety Management

## Modules

| Module | Description |
|--------|-------------|
| **Standards Library** | Central repository of ISO clauses and controls with cross-mapping |
| **Audit & Inspection** | Feature-rich template builder, audit library, mobile-friendly execution |
| **Risk Register** | Risk identification, assessment, controls, and mitigations |
| **Incident Reporting** | Workplace incident capture and investigation |
| **Road Traffic Collision** | Vehicle accident management |
| **Complaints** | External complaint handling with email ingestion |
| **Policy & Document Library** | Controlled documents, policies, SOPs, work instructions |
| **Dashboards & Analytics** | Cross-module reporting and analytics |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11 + FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 + Alembic |
| Authentication | JWT (Azure AD B2C ready) |
| File Storage | Azure Blob Storage |
| Hosting | Azure App Service / Container Apps |
| CI/CD | GitHub Actions |

## Project Structure

```
quality-governance-platform/
├── src/
│   ├── api/              # FastAPI routes and endpoints
│   ├── core/             # Core configuration and utilities
│   ├── domain/           # Domain models and business logic
│   ├── infrastructure/   # Database, external services
│   └── services/         # Application services
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── migrations/           # Database migrations
├── docs/                 # Documentation
└── scripts/              # Utility scripts
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/quality-governance-platform.git
cd quality-governance-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn src.main:app --reload
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## API Documentation

Once running, access the API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## License

Proprietary - All rights reserved.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
