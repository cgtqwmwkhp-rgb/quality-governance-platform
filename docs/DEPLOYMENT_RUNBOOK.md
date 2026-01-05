# Quality Governance Platform - Deployment Runbook

**Version**: 1.0  
**Last Updated**: 2026-01-05  
**Purpose**: Step-by-step guide for deploying the Quality Governance Platform in containerized environments

---

## Prerequisites

### Required Software
- Docker 20.10+ (with BuildKit support)
- docker-compose 1.29+ or Docker Compose V2
- curl (for health checks)
- PostgreSQL client (optional, for manual DB access)

### Required Access
- Docker registry access (if using private registry)
- Database credentials (for production)
- Secret keys (for production)

---

## Deployment Modes

### 1. Sandbox Deployment (Local Development)

**Purpose**: Local testing and development with ephemeral data

**Command**:
```bash
docker-compose -f docker-compose.sandbox.yml up -d
```

**Configuration**:
- Uses inline environment variables in `docker-compose.sandbox.yml`
- PostgreSQL data stored in named volume `postgres_data`
- Application runs on `http://localhost:8000`
- Health check: `http://localhost:8000/healthz`

**Credentials** (Sandbox Only):
- Database: `qgp_user` / `qgp_sandbox_password`
- Database Name: `quality_governance_sandbox`
- Secret Keys: Placeholder values (not for production)

**Logs**:
```bash
docker-compose -f docker-compose.sandbox.yml logs -f app
```

**Shutdown**:
```bash
# Stop services (keep data)
docker-compose -f docker-compose.sandbox.yml down

# Stop services and remove data
docker-compose -f docker-compose.sandbox.yml down -v
```

---

### 2. Production Deployment (Azure/AWS/GCP)

**Purpose**: Production-ready deployment with external secrets management

**Steps**:

#### Step 1: Prepare Environment Variables
Create `.env.production` file (NEVER commit to repo):
```bash
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://user:password@prod-db-host:5432/quality_governance_prod
SECRET_KEY=<generate-with-secrets.token_urlsafe-32>
JWT_SECRET_KEY=<generate-with-secrets.token_urlsafe-32>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
LOG_LEVEL=INFO
CORS_ORIGINS=https://app.example.com,https://admin.example.com
DATABASE_ECHO=false
```

**Generate Secrets**:
```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

#### Step 2: Build Docker Image
```bash
docker build -t quality-governance-platform:latest .
```

**Tag for Registry**:
```bash
docker tag quality-governance-platform:latest <registry>/quality-governance-platform:<version>
docker push <registry>/quality-governance-platform:<version>
```

#### Step 3: Run Database Migrations
```bash
docker run --rm \
  --env-file .env.production \
  <registry>/quality-governance-platform:<version> \
  alembic upgrade head
```

**Verify Migration**:
```bash
docker run --rm \
  --env-file .env.production \
  <registry>/quality-governance-platform:<version> \
  alembic current
```

#### Step 4: Start Application
```bash
docker run -d \
  --name qgp-app \
  --env-file .env.production \
  -p 8000:8000 \
  --restart unless-stopped \
  <registry>/quality-governance-platform:<version>
```

#### Step 5: Verify Health
```bash
curl -f http://localhost:8000/healthz
```

**Expected Response**:
```json
{
  "status": "ok",
  "request_id": "<uuid>"
}
```

---

## Health Checks

### Liveness Probe
**Endpoint**: `GET /healthz`  
**Purpose**: Indicates if the application is alive  
**Success**: 200 OK with `{"status": "ok", "request_id": "<uuid>"}`  
**Failure**: No response or non-200 status  
**Action**: Restart container

### Readiness Probe (TODO)
**Endpoint**: `GET /readyz`  
**Purpose**: Indicates if the application is ready to accept traffic  
**Success**: 200 OK with `{"status": "ready", "database": "connected"}`  
**Failure**: 503 Service Unavailable  
**Action**: Remove from load balancer rotation

---

## Rollback Procedures

### Scenario 1: Failed Migration

**Symptoms**:
- Migration container exits with non-zero code
- Application fails to start with database errors

**Rollback Steps**:
```bash
# 1. Identify current migration
docker run --rm --env-file .env.production <image> alembic current

# 2. Downgrade to previous version
docker run --rm --env-file .env.production <image> alembic downgrade -1

# 3. Verify downgrade
docker run --rm --env-file .env.production <image> alembic current

# 4. Restart application with previous image version
docker stop qgp-app
docker rm qgp-app
docker run -d --name qgp-app --env-file .env.production <previous-image>
```

### Scenario 2: Failed Application Deployment

**Symptoms**:
- Health check fails after deployment
- Application logs show errors

**Rollback Steps**:
```bash
# 1. Stop failed deployment
docker stop qgp-app
docker rm qgp-app

# 2. Restart with previous image version
docker run -d --name qgp-app --env-file .env.production <previous-image>

# 3. Verify health
curl -f http://localhost:8000/healthz
```

### Scenario 3: Data Corruption

**Symptoms**:
- Database integrity errors
- Audit log inconsistencies

**Rollback Steps**:
```bash
# 1. Stop application
docker stop qgp-app

# 2. Restore database from backup
pg_restore -h <db-host> -U <db-user> -d <db-name> <backup-file>

# 3. Run migrations to ensure schema is current
docker run --rm --env-file .env.production <image> alembic upgrade head

# 4. Restart application
docker start qgp-app
```

---

## Monitoring and Observability

### Application Logs
```bash
# Follow logs in real-time
docker logs -f qgp-app

# View last 100 lines
docker logs --tail 100 qgp-app

# Search for errors
docker logs qgp-app 2>&1 | grep ERROR
```

### Database Connectivity
```bash
# Check database connection from application container
docker exec qgp-app python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.getenv('DATABASE_URL').replace('asyncpg', 'psycopg2'))
with engine.connect() as conn:
    print('Database connection: OK')
"
```

### Resource Usage
```bash
# Check container resource usage
docker stats qgp-app

# Check disk usage
docker system df
```

---

## Troubleshooting

### Issue: Health Check Fails

**Diagnosis**:
```bash
# Check application logs
docker logs qgp-app

# Check if port is listening
docker exec qgp-app netstat -tlnp | grep 8000

# Manual health check
docker exec qgp-app curl -f http://localhost:8000/healthz
```

**Common Causes**:
- Database connection failure (check DATABASE_URL)
- Missing environment variables (check .env.production)
- Application startup errors (check logs)

### Issue: Migration Fails

**Diagnosis**:
```bash
# Check migration logs
docker logs qgp-migrate-sandbox

# Check current migration state
docker run --rm --env-file .env.production <image> alembic current

# Check migration history
docker run --rm --env-file .env.production <image> alembic history
```

**Common Causes**:
- Database schema conflicts (manual schema changes)
- Missing migration dependencies (out-of-order migrations)
- Database connection failure

### Issue: Configuration Validation Fails

**Diagnosis**:
```bash
# Check application startup logs
docker logs qgp-app | head -50
```

**Common Causes**:
- SECRET_KEY or JWT_SECRET_KEY using placeholder values in production
- DATABASE_URL using localhost/127.0.0.1 in production
- APP_ENV not set to 'production'

**Fix**:
- Update .env.production with correct values
- Restart container with updated environment

---

## Security Checklist

### Pre-Deployment
- [ ] All secrets generated with cryptographically secure random values
- [ ] `.env.production` file has restricted permissions (600)
- [ ] No secrets committed to version control
- [ ] APP_ENV set to 'production'
- [ ] DATABASE_URL uses TLS/SSL connection
- [ ] CORS_ORIGINS restricted to known domains

### Post-Deployment
- [ ] Health check endpoint accessible
- [ ] Application logs show no errors
- [ ] Database migrations applied successfully
- [ ] No placeholder secrets in use (verified by startup validation)
- [ ] Container running as non-root user (verified by `docker exec qgp-app whoami`)

---

## Maintenance

### Backup Database
```bash
# Create backup
docker exec qgp-postgres-sandbox pg_dump -U qgp_user quality_governance_sandbox > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker exec -i qgp-postgres-sandbox psql -U qgp_user quality_governance_sandbox < backup_20260105_120000.sql
```

### Update Application
```bash
# 1. Pull new image
docker pull <registry>/quality-governance-platform:<new-version>

# 2. Run migrations
docker run --rm --env-file .env.production <registry>/quality-governance-platform:<new-version> alembic upgrade head

# 3. Stop old container
docker stop qgp-app
docker rm qgp-app

# 4. Start new container
docker run -d --name qgp-app --env-file .env.production <registry>/quality-governance-platform:<new-version>

# 5. Verify health
curl -f http://localhost:8000/healthz
```

### Clean Up Old Images
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune
```

---

## Emergency Contacts

**Platform Owner**: [TBD]  
**Database Administrator**: [TBD]  
**DevOps Team**: [TBD]  
**On-Call Rotation**: [TBD]

---

## Appendix: Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | Yes | `development` | Application environment mode |
| `DATABASE_URL` | Yes | None | PostgreSQL connection string |
| `SECRET_KEY` | Yes | None | Application secret key |
| `JWT_SECRET_KEY` | Yes | None | JWT signing key |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token expiration |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token expiration |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | Allowed CORS origins |
| `DATABASE_ECHO` | No | `false` | Enable SQL query logging |
