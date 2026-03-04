# Architecture

## Overview

QGP is a quality governance platform built as a monorepo with three main components:

| Component  | Tech              | Location      |
|------------|-------------------|---------------|
| Backend    | FastAPI (Python)  | `src/`        |
| Frontend   | React + TypeScript| `frontend/`   |
| Database   | PostgreSQL 15     | Managed Azure |

All requests flow through the FastAPI backend, which serves as the API layer. The React frontend is deployed as a static web app and communicates via REST.

## Directory Structure

```
├── src/
│   ├── api/              # Route handlers grouped by module
│   │   ├── incidents.py
│   │   ├── complaints.py
│   │   └── ...
│   ├── domain/           # Business logic, services, schemas
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   └── services/     # Business logic layer
│   ├── core/             # App config, security, middleware
│   │   ├── config.py     # Settings via pydantic-settings
│   │   ├── security.py   # JWT + Azure AD token validation
│   │   └── middleware.py # CORS, logging, error handling
│   ├── infrastructure/   # External integrations
│   │   ├── database.py   # SQLAlchemy engine + session
│   │   └── azure/        # Blob storage, email, etc.
│   └── main.py           # FastAPI app entrypoint
├── frontend/
│   └── src/
│       ├── components/   # Reusable UI components
│       ├── pages/        # Route-level page components
│       ├── hooks/        # Custom React hooks
│       ├── stores/       # Zustand state stores
│       ├── api/          # Axios API client + typed endpoints
│       └── utils/        # Shared helpers
├── tests/
│   ├── unit/             # Isolated unit tests
│   └── integration/      # Tests hitting the database
├── alembic/              # Database migrations
├── scripts/              # Dev and CI helper scripts
└── infra/                # IaC (Bicep / Terraform)
```

## Data Flow

```
Client (Browser)
  │
  ▼
React SPA ──HTTP/JSON──► FastAPI Routes (src/api/)
                              │
                              ▼
                         Services (src/domain/services/)
                              │
                              ▼
                         Models (src/domain/models/)
                              │
                              ▼
                         PostgreSQL
```

1. The React frontend sends typed API requests via Axios.
2. FastAPI route handlers validate input with Pydantic schemas.
3. Services contain all business logic — routes stay thin.
4. SQLAlchemy models map to database tables; Alembic manages migrations.
5. Responses are serialized back through Pydantic schemas.

## Authentication

```
Browser → Azure AD login → ID token + access token
  │
  ▼
Frontend stores tokens, sends access token as Bearer header
  │
  ▼
Backend validates JWT signature against Azure AD JWKS endpoint
  │
  ▼
User identity extracted → role-based access control applied
```

- **Provider:** Azure Active Directory (Entra ID) with SSO
- **Token format:** JWT (RS256, validated against Azure AD JWKS)
- **Session:** Stateless — no server-side sessions; tokens carry claims
- **Roles:** Mapped from Azure AD groups to application permissions

## Key Patterns

### Repository Pattern
Database access is abstracted behind repository classes in the service layer. Services never call SQLAlchemy directly from route handlers — they go through typed repository methods that return domain models.

### Dependency Injection
FastAPI's `Depends()` system wires up database sessions, current-user resolution, and service instances. This keeps route handlers free of setup boilerplate and makes testing straightforward via overrides.

### Event-Driven Audit Logging
State changes (create, update, delete, status transitions) emit domain events that are captured by an audit logging listener. Every mutation is recorded with who, what, when, and the before/after state.

## Module Map

| Module          | Description                                | Key Entities                |
|-----------------|--------------------------------------------|-----------------------------|
| Incidents       | Workplace incident tracking and response   | Incident, IncidentAction    |
| Complaints      | Customer/internal complaint management     | Complaint, ComplaintAction   |
| Risks           | Risk register and assessment               | Risk, RiskAssessment        |
| Audits          | Internal/external audit scheduling         | Audit, AuditFinding         |
| CAPA            | Corrective & preventive actions            | CAPA, CAPAAction            |
| Policies        | Policy lifecycle and approvals             | Policy, PolicyVersion       |
| Documents       | Controlled document management             | Document, DocumentRevision  |
| Investigations  | Root cause analysis workflows              | Investigation, Finding      |
| Near-Misses     | Near-miss reporting and trending           | NearMiss                    |
| RTAs            | Road traffic accident records              | RTA, RTAAction              |

## Infrastructure

```
┌──────────────────────────────────────────────────┐
│                    Azure Cloud                    │
│                                                   │
│  ┌─────────────────┐    ┌──────────────────────┐ │
│  │  Azure Static    │    │  Azure Container     │ │
│  │  Web Apps        │    │  Apps                 │ │
│  │  (React SPA)     │───►│  (FastAPI backend)   │ │
│  └─────────────────┘    └──────────┬───────────┘ │
│                                     │             │
│                          ┌──────────▼───────────┐ │
│                          │  Azure Database for   │ │
│                          │  PostgreSQL (Flex)     │ │
│                          └──────────────────────┘ │
│                                                   │
│  ┌─────────────────┐    ┌──────────────────────┐ │
│  │  Azure Blob      │    │  Azure AD (Entra ID) │ │
│  │  Storage          │    │  SSO + RBAC          │ │
│  └─────────────────┘    └──────────────────────┘ │
└──────────────────────────────────────────────────┘
```

- **Compute:** Azure Container Apps (backend) with auto-scaling
- **Frontend hosting:** Azure Static Web Apps with global CDN
- **Database:** Azure Database for PostgreSQL Flexible Server
- **Storage:** Azure Blob Storage for file attachments
- **Auth:** Azure AD (Entra ID) for SSO and role management
- **CI/CD:** GitHub Actions → build, test, deploy to staging/production
