# D0 Rehearsal Runbook: External Execution Guide

**Purpose**: Execute Stage D0 rehearsal and reset drill scripts on a Docker-enabled host to capture evidence for Gate 1.

**Audience**: Repository owner, DevOps engineer, or anyone with Docker access

**Prerequisites**:
- Docker installed and running (version 20.10+)
- Docker Compose installed (version 2.0+)
- Git repository cloned locally
- Terminal access (bash or compatible shell)

---

## Overview

This runbook guides you through executing two scripts:
1. **Rehearsal Script** (`rehearsal_containerized_deploy.sh`): Simulates a full deployment
2. **Reset Drill Script** (`reset_drill.sh`): Simulates disaster recovery

**Time Required**: ~15-20 minutes total

**Evidence Required**: Terminal outputs, health check responses, API test results, logs

---

## Pre-Execution Checklist

Before starting, verify:

- [ ] Docker is installed and running
  ```bash
  docker --version
  docker compose version
  docker ps  # Should not error
  ```

- [ ] Repository is cloned and up to date
  ```bash
  cd /path/to/quality-governance-platform
  git status
  git log -1 --oneline  # Record this commit SHA
  ```

- [ ] No conflicting containers or volumes
  ```bash
  docker ps -a | grep qgp
  docker volume ls | grep qgp
  # If any exist, remove them:
  # docker rm -f $(docker ps -aq --filter "name=qgp")
  # docker volume rm $(docker volume ls -q --filter "name=qgp")
  ```

- [ ] Scripts are executable
  ```bash
  ls -la scripts/rehearsal_containerized_deploy.sh
  ls -la scripts/reset_drill.sh
  # If not executable:
  # chmod +x scripts/rehearsal_containerized_deploy.sh scripts/reset_drill.sh
  ```

- [ ] Evidence template is ready
  ```bash
  ls -la docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md
  ```

---

## Part 1: Rehearsal Script Execution

### Step 1: Record Environment Details

Open the evidence template and fill in:
- Operating System (e.g., `uname -a`)
- Docker version (e.g., `docker --version`)
- Docker Compose version (e.g., `docker compose version`)
- Git commit SHA (e.g., `git log -1 --oneline`)
- Execution date (e.g., `date`)

### Step 2: Execute Rehearsal Script

**Command**:
```bash
cd /path/to/quality-governance-platform
./scripts/rehearsal_containerized_deploy.sh 2>&1 | tee rehearsal_output.log
```

**What This Does**:
- Cleans up any existing containers
- Starts PostgreSQL
- Waits for PostgreSQL to be ready
- Runs database migrations
- Starts the application
- Waits for application to be ready
- Runs health checks (`/healthz` and `/readyz`)
- Runs smoke API tests (403, 201, 409)

**Expected Output**:
```
✅ Step 1: Clean up any existing containers
✅ Step 2: Start PostgreSQL
✅ Step 3: Wait for PostgreSQL to be ready
✅ Step 4: Run migrations
✅ Step 5: Start application
✅ Step 6: Wait for application to be ready
✅ Step 7: Health checks
✅ Step 8: Smoke API tests

🎉 Rehearsal completed successfully!
```

**Duration**: ~3-5 minutes

### Step 3: Verify Health Endpoints

**Test `/healthz`**:
```bash
curl http://localhost:8000/healthz | jq
```

**Expected Response**:
```json
{
  "status": "ok",
  "request_id": "12345678-1234-1234-1234-123456789abc"
}
```

**Test `/readyz`**:
```bash
curl http://localhost:8000/readyz | jq
```

**Expected Response** (if DB check implemented):
```json
{
  "status": "ready",
  "database": "connected",
  "request_id": "12345678-1234-1234-1234-123456789abc"
}
```

**Expected Response** (if DB check not yet implemented):
```json
{
  "status": "ready",
  "request_id": "12345678-1234-1234-1234-123456789abc"
}
```

### Step 4: Verify Migrations

**Check Current Migration**:
```bash
docker compose -f docker-compose.sandbox.yml exec app alembic current
```

**Expected Output**:
```
abc123def456 (head)
```

**Check Database Tables**:
```bash
docker compose -f docker-compose.sandbox.yml exec postgres psql -U qgp_user -d qgp_db -c "\dt"
```

**Expected Output**:
```
                List of relations
 Schema |         Name          | Type  |  Owner   
--------+-----------------------+-------+----------
 public | alembic_version       | table | qgp_user
 public | audit_events          | table | qgp_user
 public | complaints            | table | qgp_user
 public | incidents             | table | qgp_user
 public | permissions           | table | qgp_user
 public | policies              | table | qgp_user
 public | roles                 | table | qgp_user
 public | users                 | table | qgp_user
 ...
```

### Step 5: Run Smoke API Tests

**Test 1: RBAC Deny (403)**:
```bash
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Policy", "content": "Test content"}' \
  | jq
```

**Expected**:
- Status code: 403
- Response includes `error.code`, `error.message`, `error.request_id`

---

**Test 2: Create Policy (201)** (requires authentication):

*Note: If authentication is not yet implemented, skip this test and document in evidence.*

```bash
# First, create a test user or get a valid token
# Then:
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid-token>" \
  -d '{"title": "Test Policy", "content": "Test content", "effective_date": "2026-01-01"}' \
  | jq
```

**Expected**:
- Status code: 201
- Response includes `id`, `title`, `reference_number`
- Audit event created with `request_id`

---

**Test 3: Duplicate Policy (409)**:

*Note: Only run if Test 2 succeeded.*

```bash
# Repeat the same POST request as Test 2
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid-token>" \
  -d '{"title": "Test Policy", "content": "Test content", "effective_date": "2026-01-01"}' \
  | jq
```

**Expected**:
- Status code: 409
- Response includes `error.code` (e.g., "DUPLICATE_REFERENCE_NUMBER")
- Response includes `error.request_id`

### Step 6: Review Application Logs

**Command**:
```bash
docker compose -f docker-compose.sandbox.yml logs app | tail -50
```

**Look For**:
- No errors during startup
- Migration success messages (e.g., "Running upgrade ... -> abc123")
- Health check requests (e.g., "GET /healthz" "GET /readyz")
- API request logs with `request_id`

**Save Logs**:
```bash
docker compose -f docker-compose.sandbox.yml logs app > app_logs.log
docker compose -f docker-compose.sandbox.yml logs postgres > postgres_logs.log
```

### Step 7: Copy Outputs to Evidence Template

Open `docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md` and fill in:
- Part 1: Rehearsal Script Execution
  - Terminal output (from `rehearsal_output.log`)
  - Health check results
  - Migration verification
  - Smoke API test results
  - Application logs (last 50 lines or attach full logs)
- Check all success criteria boxes

---

## Part 2: Reset Drill Execution

### Step 1: Execute Reset Drill Script

**Command**:
```bash
./scripts/reset_drill.sh 2>&1 | tee reset_drill_output.log
```

**What This Does**:
- Stops all containers
- Removes containers
- Removes volumes (simulates data loss)
- Verifies clean state
- Restarts PostgreSQL
- Runs migrations from scratch
- Restarts application

**Expected Output**:
```
✅ Step 1: Stop all containers
✅ Step 2: Remove containers
✅ Step 3: Remove volumes (data loss simulation)
✅ Step 4: Verify clean state
✅ Step 5: Restart PostgreSQL
✅ Step 6: Run migrations (from scratch)
✅ Step 7: Restart application

🎉 Reset drill completed successfully!
Time taken: 3m 45s
```

**Duration**: ~3-5 minutes

### Step 2: Verify Database After Reset

**Check Tables**:
```bash
docker compose -f docker-compose.sandbox.yml exec postgres psql -U qgp_user -d qgp_db -c "\dt"
```

**Expected**: Same tables as before, but empty (except `alembic_version`)

**Check Migration Version**:
```bash
docker compose -f docker-compose.sandbox.yml exec app alembic current
```

**Expected**: Same migration revision as before reset (e.g., `abc123def456 (head)`)

### Step 3: Verify Health After Reset

**Command**:
```bash
curl http://localhost:8000/healthz | jq
```

**Expected Response**:
```json
{
  "status": "ok",
  "request_id": "87654321-4321-4321-4321-cba987654321"
}
```

### Step 4: Copy Outputs to Evidence Template

Open `docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md` and fill in:
- Part 2: Reset Drill Execution
  - Terminal output (from `reset_drill_output.log`)
  - Database verification
  - Migration version verification
  - Health check after reset
- Check all success criteria boxes
- Record time taken

---

## Part 3: Cleanup

### Step 1: Stop All Containers

**Command**:
```bash
docker compose -f docker-compose.sandbox.yml down -v
```

**Expected Output**:
```
[+] Running 3/3
 ✔ Container qgp-app       Removed
 ✔ Container qgp-postgres  Removed
 ✔ Network qgp_default     Removed
 ✔ Volume qgp_postgres_data Removed
```

### Step 2: Clean Up Docker Resources

**Command**:
```bash
docker system prune -f
```

**Expected Output**:
```
Deleted Containers:
...
Deleted Networks:
...
Total reclaimed space: ...
```

### Step 3: Copy Cleanup Output to Evidence Template

Fill in Part 3: Cleanup in the evidence template.

---

## Part 4: Finalize Evidence

### Step 1: Review Evidence Template

Open `docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md` and verify:
- [ ] All [TO BE FILLED] sections are filled
- [ ] All [PASTE ... HERE] sections have content
- [ ] All success criteria checkboxes are checked
- [ ] Overall assessment is complete
- [ ] No secrets are exposed in outputs
- [ ] Approval signatures are filled (or marked as pending)

### Step 2: Attach Raw Logs (Optional)

If terminal outputs are very long, attach raw log files:
```bash
# Create evidence/logs directory
mkdir -p docs/evidence/logs

# Move logs
mv rehearsal_output.log docs/evidence/logs/
mv reset_drill_output.log docs/evidence/logs/
mv app_logs.log docs/evidence/logs/
mv postgres_logs.log docs/evidence/logs/
```

Update the evidence template to reference these files in the Appendix.

### Step 3: Commit Evidence

**Commands**:
```bash
git add docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md
git add docs/evidence/logs/  # If logs are attached
git commit -m "Add Stage D0 rehearsal execution evidence

- Rehearsal script executed successfully
- Reset drill executed successfully
- All success criteria met
- Evidence captured: terminal outputs, health checks, API tests, logs

Gate 1: MET"
git push origin main
```

---

## Troubleshooting

### Issue: Docker is not running

**Symptoms**:
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

**Solution**:
```bash
# Linux
sudo systemctl start docker

# macOS
# Start Docker Desktop from Applications

# Windows
# Start Docker Desktop from Start Menu
```

---

### Issue: Port 8000 is already in use

**Symptoms**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use
```

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill the process or change the port in docker-compose.sandbox.yml
```

---

### Issue: PostgreSQL fails to start

**Symptoms**:
```
postgres    | FATAL:  database files are incompatible with server
```

**Solution**:
```bash
# Remove existing volumes and start fresh
docker compose -f docker-compose.sandbox.yml down -v
docker compose -f docker-compose.sandbox.yml up -d
```

---

### Issue: Migrations fail

**Symptoms**:
```
alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'
```

**Solution**:
```bash
# Check if migrations directory exists
ls -la migrations/versions/

# If missing, ensure you're on the correct branch
git status
git log -1 --oneline

# Try running migrations manually
docker compose -f docker-compose.sandbox.yml exec app alembic upgrade head
```

---

### Issue: Health check returns 503

**Symptoms**:
```json
{
  "status": "not_ready",
  "database": "disconnected",
  "error": "connection refused"
}
```

**Solution**:
```bash
# Check if PostgreSQL is running
docker compose -f docker-compose.sandbox.yml ps

# Check PostgreSQL logs
docker compose -f docker-compose.sandbox.yml logs postgres

# Verify database connection string in .env.sandbox
cat .env.sandbox | grep DATABASE_URL
```

---

### Issue: API tests return 500 errors

**Symptoms**:
```json
{
  "detail": "Internal Server Error"
}
```

**Solution**:
```bash
# Check application logs for errors
docker compose -f docker-compose.sandbox.yml logs app | tail -100

# Common causes:
# - Database connection issues
# - Missing environment variables
# - Migration not applied
# - Code errors
```

---

### Issue: Smoke API tests fail due to authentication

**Symptoms**:
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid authentication token"
  }
}
```

**Solution**:
- If authentication is not yet implemented, document this in the evidence template
- Mark Test 2 and Test 3 as "SKIPPED - Authentication not yet implemented"
- This is acceptable for Stage D0 rehearsal

---

## Success Criteria Summary

**Rehearsal Script**:
- [ ] All 8 steps completed successfully
- [ ] PostgreSQL started and ready
- [ ] Migrations applied successfully
- [ ] Application started and healthy
- [ ] `/healthz` returns 200 OK
- [ ] `/readyz` returns 200 OK (or 503 if DB check fails)
- [ ] RBAC deny returns 403 with canonical error envelope
- [ ] Create policy returns 201 (or skipped if auth not implemented)
- [ ] Duplicate policy returns 409 (or skipped if auth not implemented)
- [ ] All responses include `request_id`
- [ ] No errors in application logs

**Reset Drill**:
- [ ] All 7 steps completed successfully
- [ ] Containers stopped and removed
- [ ] Volumes removed (data loss confirmed)
- [ ] PostgreSQL restarted successfully
- [ ] Migrations applied from scratch
- [ ] Application restarted and healthy
- [ ] `/healthz` returns 200 OK after reset
- [ ] Database tables recreated correctly

**Evidence Quality**:
- [ ] Full terminal outputs captured
- [ ] All health check responses recorded
- [ ] Smoke API test results documented
- [ ] Migration verification included
- [ ] Application logs reviewed
- [ ] No secrets exposed in outputs

---

## Next Steps

After completing this runbook and filling in the evidence template:

1. ✅ Commit evidence to repository
2. ✅ Verify Gate 1 is met
3. ➡️ Proceed to Phase 2: Azure staging prerequisites
4. ➡️ Execute Azure staging deployment (Phase 3)

---

## References

- **Rehearsal Script**: `scripts/rehearsal_containerized_deploy.sh`
- **Reset Drill Script**: `scripts/reset_drill.sh`
- **Evidence Template**: `docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md`
- **Deployment Runbook**: `docs/DEPLOYMENT_RUNBOOK.md`
- **Docker Compose Config**: `docker-compose.sandbox.yml`

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-05  
**Maintained By**: Platform Team
