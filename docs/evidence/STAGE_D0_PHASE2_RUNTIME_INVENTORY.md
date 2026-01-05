# Stage D0 Phase 2: Runtime Inventory

**Date**: 2026-01-05  
**Purpose**: Document production start command, env vars, and migration command for containerization

---

## Production Start Command

**Command**:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Details**:
- **Entry Point**: `src.main:app` (FastAPI application instance)
- **Host**: `0.0.0.0` (bind to all interfaces for container access)
- **Port**: `8000` (default HTTP port for the application)
- **Workers**: Single worker (can be scaled via container replicas or `--workers` flag)

**Alternative** (with workers for production):
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Health Endpoints

**Liveness Probe**: `/healthz`
- **Purpose**: Indicates if the application is alive and should not be restarted
- **Returns**: `{"status": "ok", "request_id": "<uuid>"}` (200 OK)
- **Implementation**: `src/main.py` line 31-37

**Readiness Probe**: `/readyz`
- **Purpose**: Indicates if the application is ready to accept traffic (database connected)
- **Returns**: `{"status": "ready", "database": "connected"}` (200 OK) or 503 if not ready
- **Implementation**: Not yet implemented (TODO for D0 Phase 3)
- **Recommended**: Add database ping check before returning ready status

---

## Required Environment Variables

### Critical (MUST be set)

1. **APP_ENV**
   - **Purpose**: Application environment mode
   - **Values**: `development`, `staging`, `production`
   - **Default**: `development`
   - **Production**: MUST be `production` to enable security validations

2. **DATABASE_URL**
   - **Purpose**: PostgreSQL connection string
   - **Format**: `postgresql+asyncpg://user:password@host:port/database`
   - **Example**: `postgresql+asyncpg://postgres:password@postgres:5432/quality_governance`
   - **Production**: MUST NOT use localhost/127.0.0.1 (enforced by config validation)

3. **SECRET_KEY**
   - **Purpose**: Application secret key for session/cookie signing
   - **Generation**: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
   - **Production**: MUST NOT use placeholder values (enforced by config validation)

4. **JWT_SECRET_KEY**
   - **Purpose**: JWT token signing and verification
   - **Generation**: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
   - **Production**: MUST NOT use placeholder values (enforced by config validation)

### Optional (with defaults)

5. **JWT_ALGORITHM**
   - **Default**: `HS256`
   - **Purpose**: JWT signing algorithm

6. **JWT_ACCESS_TOKEN_EXPIRE_MINUTES**
   - **Default**: `30`
   - **Purpose**: Access token expiration time

7. **JWT_REFRESH_TOKEN_EXPIRE_DAYS**
   - **Default**: `7`
   - **Purpose**: Refresh token expiration time

8. **LOG_LEVEL**
   - **Default**: `INFO`
   - **Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

9. **CORS_ORIGINS**
   - **Default**: `["http://localhost:3000", "http://localhost:8080"]`
   - **Purpose**: Allowed CORS origins (comma-separated)

10. **DATABASE_ECHO**
    - **Default**: `false`
    - **Purpose**: Enable SQLAlchemy query logging (debug only)

### Future/Optional (not yet implemented)

11. **AZURE_STORAGE_CONNECTION_STRING** - Azure Blob Storage for attachments
12. **AZURE_STORAGE_CONTAINER_NAME** - Blob container name
13. **EMAIL_IMAP_SERVER** - Email ingestion server
14. **EMAIL_IMAP_PORT** - Email ingestion port
15. **EMAIL_USERNAME** - Email ingestion username
16. **EMAIL_PASSWORD** - Email ingestion password

---

## Migration Command

**Command**:
```bash
alembic upgrade head
```

**Details**:
- **Tool**: Alembic (database migration tool)
- **Config**: `alembic.ini` (in repository root)
- **Migrations**: `alembic/versions/` directory
- **Environment**: `alembic/env.py` (uses DATABASE_URL from environment)

**Pre-Migration Check** (optional but recommended):
```bash
alembic current  # Show current revision
alembic history  # Show migration history
```

**Migration Strategy**:
- Run migrations BEFORE starting the application
- Use a separate "migrate" container/job in docker-compose
- Application container should depend on successful migration completion

---

## Configuration Validation

**Startup Validation** (enforced by `src/core/config.py`):
- ✅ SECRET_KEY must not be a placeholder in production
- ✅ JWT_SECRET_KEY must not be a placeholder in production
- ✅ DATABASE_URL must not use localhost/127.0.0.1 in production
- ✅ DATABASE_URL must start with `postgresql` or `sqlite`
- ✅ APP_ENV must be explicitly set for production deployments

**Failure Behavior**:
- Application will **refuse to start** if validation fails
- Clear error messages guide the operator to fix the issue

---

## Gate 2: ✅ PASS

- Start command explicitly stated: `uvicorn src.main:app --host 0.0.0.0 --port 8000`
- Health endpoints documented: `/healthz` (liveness), `/readyz` (readiness - TODO)
- Required env vars enumerated: APP_ENV, DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY
- Migration command explicitly stated: `alembic upgrade head`
- Configuration validation enforced at startup
