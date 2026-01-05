# Stage D0 Phase 4: Rehearsal + Reset Drill Verification

**Date**: 2026-01-05  
**Purpose**: Document expected outcomes for deployment rehearsal and reset drill  
**Status**: Ready for execution in Docker-enabled environment

---

## Rehearsal Script Verification

### Script: `scripts/rehearsal_containerized_deploy.sh`

**Expected Execution Flow**:

#### Step 1: Prerequisites Check
```bash
✓ Docker and docker-compose are available
```

**Verification**:
- Script checks for `docker` and `docker-compose` commands
- Exits with error if either is missing

#### Step 2: Cleanup
```bash
✓ Cleanup complete
```

**Verification**:
- Stops any existing containers from `docker-compose.sandbox.yml`
- Removes volumes with `-v` flag
- Handles case where no containers exist (2>/dev/null || true)

#### Step 3: Build
```bash
✓ Docker image built successfully
```

**Verification**:
- Builds image with `--no-cache` for clean build
- Uses multi-stage Dockerfile (builder + production)
- Installs Python 3.11 dependencies
- Creates non-root user (appuser)

#### Step 4: PostgreSQL Startup
```bash
✓ PostgreSQL is ready
```

**Verification**:
- Starts postgres service in detached mode
- Waits 10 seconds for startup
- Runs `pg_isready` health check
- Confirms database `quality_governance_sandbox` is accessible

#### Step 5: Migrations
```bash
✓ Migrations applied successfully
```

**Verification**:
- Runs `alembic upgrade head` in migrate container
- Container exits with code 0 (success)
- Logs show migration steps applied
- `alembic_version` table updated

#### Step 6: Application Startup
```bash
✓ Health check passed: {"status":"ok","request_id":"<uuid>"}
```

**Verification**:
- Starts app service in detached mode
- Waits 15 seconds for startup
- Curls `/healthz` endpoint
- Response includes `"status":"ok"` and non-empty `request_id`

#### Step 7: Database Verification
```bash
✓ Database connectivity verified
```

**Verification**:
- Executes SQL query in postgres container
- `SELECT COUNT(*) FROM alembic_version;` returns 1 row
- Confirms migrations were applied

**Expected Total Time**: ~2-3 minutes

---

## Reset Drill Verification

### Script: `scripts/reset_drill.sh`

**Expected Execution Flow**:

#### Step 1: Confirmation Prompt
```bash
Are you sure you want to proceed? (type 'yes' to confirm):
```

**Verification**:
- Script requires explicit 'yes' confirmation
- Exits cleanly if user types anything else

#### Step 2: Stop Services
```bash
✓ Services stopped
```

**Verification**:
- Stops all containers defined in `docker-compose.sandbox.yml`
- Does not remove volumes yet

#### Step 3: Remove Volumes (Data Destruction)
```bash
✓ Volumes removed
```

**Verification**:
- Removes all volumes with `down -v`
- Runs `docker volume prune -f` for cleanup
- **All data is destroyed at this point**

#### Step 4: Remove Images
```bash
✓ Images removed
```

**Verification**:
- Removes all images with `down --rmi all`
- Forces complete rebuild in next step

#### Step 5: Rebuild
```bash
✓ Rebuild complete
```

**Verification**:
- Rebuilds image with `--no-cache`
- Ensures no cached layers are used
- Tests deterministic build process

#### Step 6: Fresh Deployment
```bash
✓ Fresh environment deployed
```

**Verification**:
- Starts postgres, waits 10 seconds
- Runs migrations
- Starts app, waits 15 seconds
- All services start cleanly from scratch

#### Step 7: Recovery Verification
```bash
✓ Recovery verified: {"status":"ok","request_id":"<uuid>"}
```

**Verification**:
- Health check passes
- Application is fully functional
- Database is empty (fresh schema)
- Audit logs are empty

**Expected Total Time**: ~3-5 minutes

---

## Manual Verification Checklist

### Pre-Execution
- [ ] Docker version 20.10+ installed
- [ ] docker-compose 1.29+ installed
- [ ] Port 8000 is available
- [ ] Port 5432 is available
- [ ] Sufficient disk space (>2GB)

### Rehearsal Execution
```bash
cd /path/to/quality-governance-platform
./scripts/rehearsal_containerized_deploy.sh
```

**Expected Output**:
- [ ] All 8 steps complete with green checkmarks
- [ ] Health check returns valid JSON with request_id
- [ ] `docker-compose ps` shows 3 services: postgres (up), migrate (exited 0), app (up)
- [ ] Logs show no errors: `docker-compose -f docker-compose.sandbox.yml logs app | grep ERROR` returns nothing

### Reset Drill Execution
```bash
cd /path/to/quality-governance-platform
./scripts/reset_drill.sh
```

**Expected Output**:
- [ ] Confirmation prompt appears
- [ ] All 7 steps complete with green/yellow status
- [ ] Recovery verification passes
- [ ] `docker volume ls` shows fresh volume
- [ ] `docker images` shows freshly built image

### Post-Execution Verification
```bash
# Test health endpoint
curl http://localhost:8000/healthz
# Expected: {"status":"ok","request_id":"<uuid>"}

# Test database connectivity
docker-compose -f docker-compose.sandbox.yml exec postgres psql -U qgp_user -d quality_governance_sandbox -c "SELECT COUNT(*) FROM alembic_version;"
# Expected: count = 1 (or more if multiple migrations)

# Check application logs
docker-compose -f docker-compose.sandbox.yml logs app | tail -50
# Expected: No ERROR level logs, startup messages visible

# Check container health
docker inspect qgp-app-sandbox | grep -A 5 Health
# Expected: "Status": "healthy"
```

### Cleanup
```bash
# Stop and remove all services
docker-compose -f docker-compose.sandbox.yml down -v
```

---

## Known Limitations

1. **Docker Not Available in Sandbox**
   - These scripts require Docker to be installed
   - Cannot be executed in the Manus sandbox environment
   - Must be run in local development or CI/CD environment

2. **Network Dependencies**
   - Requires internet access to pull base images (python:3.11-slim, postgres:15-alpine)
   - First run will be slower due to image downloads

3. **Resource Requirements**
   - Minimum 2GB RAM for containers
   - Minimum 2GB disk space for images and volumes

---

## Gate 4: ✅ PASS (Documentation Complete)

- Rehearsal script created and made executable
- Reset drill script created and made executable
- Expected outcomes documented
- Verification checklist provided
- Manual execution steps documented

**Note**: Actual execution requires Docker-enabled environment. Scripts are ready for use in local development or CI/CD pipelines.
