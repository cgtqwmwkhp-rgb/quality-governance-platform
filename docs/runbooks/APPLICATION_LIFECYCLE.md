# Application Lifecycle Runbook

**Purpose**: Safe application startup, shutdown, and restart procedures  
**Audience**: DevOps, SRE, Operations  
**Last Updated**: 2026-01-04

---

## Application Overview

**Name**: Quality Governance Platform  
**Stack**: FastAPI + PostgreSQL + Uvicorn  
**Port**: 8000 (default)  
**Health Endpoints**: `/healthz`, `/readyz`

---

## Startup Procedure

### 1. Pre-Start Checks

```bash
# Verify environment configuration
test -f .env && echo "✓ .env file exists" || echo "✗ .env file missing"

# Verify database connectivity
pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER

# Check database migration status
alembic current
```

---

### 2. Start Application

#### Development Mode
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Mode
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

### 3. Post-Start Validation

```bash
# Check liveness
curl -f http://localhost:8000/healthz

# Check readiness
curl -f http://localhost:8000/readyz

# Check logs
tail -n 50 logs/app.log
```

---

## Shutdown Procedure

### Graceful Shutdown
```bash
# Send SIGTERM
kill -TERM $(pgrep -f "uvicorn src.main:app")

# Wait for shutdown
sleep 10
```

---

## Health Check Reference

### Liveness: `/healthz`
Returns `{"status":"ok"}` - Process is running

### Readiness: `/readyz`
Returns `{"status":"ready","database":"connected"}` - Ready for traffic

---

## Troubleshooting

### Application Won't Start
- Check logs
- Verify port 8000 available
- Check database connection

### Database Connection Errors
- Verify database is running
- Check `.env` configuration
- Restart application
