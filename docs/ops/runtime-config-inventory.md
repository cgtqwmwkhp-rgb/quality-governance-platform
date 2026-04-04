# Runtime configuration inventory

This document summarises environment variables used at runtime. **`src/core/config.py`** (`Settings`) is the **source of truth** for names, defaults, and validation; Pydantic Settings reads them from the process environment (and optional `.env` for local use).

## How configuration is sourced

| Source | Typical use |
| --- | --- |
| **`.env.example`** | Local development template; copy to `.env` (not committed). Documents many backend variables alongside `Settings`. |
| **Azure Key Vault** | Production secrets (e.g. `SECRET_KEY`, `JWT_SECRET_KEY`, DB URLs, peppers, API keys, storage connection strings). Referenced from App Service / Container Apps configuration. |
| **Azure App Service / Container Apps settings** | Non-secret or reference-backed settings: `APP_ENV`, feature toggles, URLs, CORS allowlists, Application Insights connection string references, etc. |

Exact Key Vault secret names and slot assignments are environment-specific; align new variables with `Settings` field names (uppercase env names).

## Required environments (legend)

| Tag | Meaning |
| --- | --- |
| **All** | Should be set explicitly in every deployed environment (value may differ). |
| **Dev** | Local / developer machines. |
| **Non-prod** | Staging, test, UAT. |
| **Prod** | Production. |
| **Optional** | Omitted in many setups; feature degrades gracefully or path is disabled. |

---

## Application

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `APP_NAME` | Human-readable application name. | App Service / `.env.example` | All |
| `APP_ENV` | Environment label (`development`, `production`, etc.); drives production validation. | App Service / `.env.example` | All |
| `DEBUG` | FastAPI/debug behaviour; must be off in production. | `.env.example` / App Service | Dev optional; **false in Prod** |
| `SECRET_KEY` | App secret key (sessions/signing); must not be placeholder in production. | Key Vault / `.env.example` | All (strong value in Prod) |
| `FRONTEND_URL` | Base URL for links (e.g. password reset, email CTAs). | App Service / `.env.example` | Non-prod + Prod |
| `DEFAULT_TENANT_ID` | Default tenant for unauthenticated/public portal intake. | App Service | Optional |
| `APP_VERSION` | Application version string (e.g. telemetry). | App Service / build | All |
| `LOG_LEVEL` | Python logging level. | App Service / `.env.example` | All |
| `UAT_MODE` | `READ_ONLY` or `READ_WRITE`; production defaults to read-only when unset. | App Service | Prod |
| `UAT_ADMIN_USERS` | Comma-separated user IDs allowed UAT override writes. | App Service | Optional |
| `EMAIL_IMAP_SERVER`, `EMAIL_IMAP_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD` | IMAP ingestion for email-driven workflows. | Key Vault / App Service | Optional |

---

## Database

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `DATABASE_URL` | Primary SQLAlchemy/async URL (`postgresql+asyncpg://…` or `sqlite`). | Key Vault / `.env.example` | All (non-localhost in Prod) |
| `DATABASE_ECHO` | SQL echo for debugging. | `.env.example` | Dev optional |
| `PAMS_DATABASE_URL` | Read-only MySQL URL for PAMS / Van Checklists integration. | Key Vault | Optional |
| `PAMS_SSL_CA` | CA bundle path/material for PAMS TLS. | Key Vault / App Service | Optional |

---

## Redis

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `REDIS_URL` | Redis for idempotency middleware (and related use). | Key Vault / `.env.example` | Optional |
| `CELERY_BROKER_URL` | Celery broker (often Redis). | Key Vault / `.env.example` | Optional |
| `CELERY_RESULT_BACKEND` | Celery result backend. | Key Vault / `.env.example` | Optional |

---

## Auth / JWT

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | Signing key for JWT; must not be placeholder in production. | Key Vault / `.env.example` | All |
| `JWT_ALGORITHM` | JWT algorithm (default HS256). | `.env.example` / App Service | All |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime. | App Service / `.env.example` | All |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime. | App Service / `.env.example` | All |
| `AZURE_CLIENT_ID` | Microsoft Entra application (client) ID for token validation. | Key Vault / `.env.example` | Prod (if Azure AD SSO) |
| `AZURE_TENANT_ID` | Entra tenant ID. | Key Vault / `.env.example` | Prod (if Azure AD SSO) |
| `AZURE_AD_JWKS_CACHE_TTL_SECONDS` | JWKS cache TTL for Azure AD validator. | App Service | Optional |

Frontend Azure AD variables (`VITE_*`) are documented in **`frontend/.env.example`**; they are not defined on `Settings` in `config.py`.

---

## CORS

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `CORS_ORIGINS` | JSON array or comma-separated list of allowed browser origins (production allowlist). | App Service / `.env.example` | Non-prod + Prod |

---

## GDPR

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `PSEUDONYMIZATION_PEPPER` | Secret pepper for pseudonymization; min length enforced; no placeholders in production. | Key Vault / `.env.example` | All |

---

## Telemetry

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `OTEL_TRACE_SAMPLE_RATE` | OpenTelemetry trace sampling rate. | App Service | Optional |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure Monitor / Application Insights connection string. | Key Vault / `.env.example` | Optional |

---

## Feature flags

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `EXTERNAL_AUDIT_IMPORT_ENABLED` | Master switch for external audit import / OCR path. | App Service | All |
| `EXTERNAL_AUDIT_IMPORT_FEATURE_FLAG` | Feature-flag key for staged rollout. | App Service | Optional |
| `MISTRAL_API_KEY` | Mistral API credential for OCR. | Key Vault | Optional |
| `MISTRAL_OCR_MODEL`, `MISTRAL_API_BASE_URL`, `MISTRAL_OCR_TIMEOUT_SECONDS` | Mistral OCR configuration. | App Service | Optional |
| `GOOGLE_GEMINI_API_KEY` | Optional Gemini review integration. | Key Vault | Optional |

---

## Azure

| Variable | Description | Source (typical) | Required environments |
| --- | --- | --- | --- |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection string. | Key Vault / `.env.example` | Optional (required if using blob attachments in cloud) |
| `AZURE_STORAGE_CONTAINER_NAME` | Blob container name (default `attachments`). | App Service / `.env.example` | Optional |

---

## Related documentation

- **`src/core/config.py`** — authoritative field definitions and production validation.
- **`.env.example`** — backend local template.
- **`frontend/.env.example`** — frontend build-time variables.
- **`docs/ops/SECRETS_ROTATION_RUNBOOK.md`** — secret rotation practices.

**Last updated:** 2026-04-03
