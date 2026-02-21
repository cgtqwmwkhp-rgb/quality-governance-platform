# Environment Configuration

All configuration is managed through environment variables, validated by Pydantic Settings
(`src/core/config.py`). Direct `os.getenv()` / `os.environ.get()` calls are prohibited in
application source code (`src/`) — every value must flow through the `Settings` class so
Pydantic can validate types, enforce constraints, and reject unsafe production configs at
startup (ADR-0002 fail-fast).

## Required Variables (all environments)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Async database connection string | `postgresql+asyncpg://user:pass@host/db` |
| `SECRET_KEY` | Application secret (min 16 chars in production) | *(generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)* |
| `JWT_SECRET_KEY` | JWT signing key (min 16 chars in production) | *(generate separately from SECRET_KEY)* |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | Environment name (`development`, `staging`, `production`) |
| `APP_NAME` | `Quality Governance Platform` | Display name |
| `APP_VERSION` | `1.0.0` | Semantic version |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Python log level |
| `BUILD_SHA` | `dev` | Git commit SHA for deployed build |
| `BUILD_TIME` | `local` | ISO timestamp of build |
| `FRONTEND_URL` | `https://app-qgp-prod.azurestaticapps.net` | Frontend base URL |
| `CORS_ORIGINS` | *(see config.py)* | JSON list of allowed CORS origins |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for caching |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery task broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery result backend |
| `AZURE_STORAGE_CONNECTION_STRING` | *(empty)* | Azure Blob Storage connection |
| `AZURE_STORAGE_CONTAINER_NAME` | `attachments` | Blob container name |
| `AZURE_CLIENT_ID` | *(empty)* | Azure AD app registration client ID |
| `AZURE_TENANT_ID` | *(empty)* | Azure AD tenant ID |
| `SMTP_HOST` | `smtp.office365.com` | SMTP server for outbound email |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | *(empty)* | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | SMTP password |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key for AI features |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | *(empty)* | Azure Monitor telemetry |
| `UAT_MODE` | `READ_WRITE` | UAT safety mode (`READ_ONLY` for production) |
| `UAT_ADMIN_USERS` | *(empty)* | Comma-separated user IDs for UAT write overrides |

## Production Requirements

- `SECRET_KEY` must **not** contain placeholder values (`change-me-in-production`, `changeme`, etc.)
- `JWT_SECRET_KEY` must **not** contain placeholder values
- Both secrets must be **at least 16 characters**
- `DATABASE_URL` must **not** point to `localhost` or `127.0.0.1`
- `DATABASE_URL` must start with `postgresql` or `sqlite`
- All secrets should be sourced from **Azure Key Vault** (not hard-coded in CI)
- Violations cause immediate startup failure (fail-fast, ADR-0002)

## Development Defaults

- SQLite database (`sqlite+aiosqlite:///...`) is accepted
- Placeholder secrets are allowed (with log warnings)
- Redis is optional — cache falls back to in-memory
- No Azure services required

## Adding New Configuration

1. Add the field to the `Settings` class in `src/core/config.py` with a sensible default
2. Add a test in `tests/unit/test_config_validation.py` verifying the default
3. If production-critical, add validation in `_validate_production_settings()`
4. Update this document
5. **Never** use `os.getenv()` directly in `src/` — always use `settings.field_name`
