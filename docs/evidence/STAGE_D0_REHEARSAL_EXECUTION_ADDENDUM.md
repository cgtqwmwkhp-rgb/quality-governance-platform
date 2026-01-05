# Stage D0: Rehearsal Execution Evidence Addendum

**Stage**: D0 (Containerization + Deployment Readiness)  
**Date**: [TO BE FILLED]  
**Executor**: [TO BE FILLED]  
**Status**: ⏳ PENDING EXECUTION

---

## Purpose

This document captures evidence from **actual execution** of the D0 rehearsal and reset drill scripts on a Docker-enabled host. This evidence is required to meet **Gate 1** before proceeding to Azure staging deployment.

**Gate 1 Requirement**: D0 rehearsal and reset drill must be executed and evidenced (not just documented).

---

## Execution Environment

**Host Details**:
- **Operating System**: [e.g., Ubuntu 22.04, macOS 14.0, Windows 11 with WSL2]
- **Docker Version**: [e.g., Docker 24.0.7]
- **Docker Compose Version**: [e.g., Docker Compose 2.23.0]
- **Git Commit SHA**: [e.g., 749cd4c]
- **Execution Date**: [e.g., 2026-01-06]

**Prerequisites Verified**:
- [ ] Docker installed and running
- [ ] Docker Compose installed
- [ ] Git repository cloned
- [ ] On correct branch/commit
- [ ] No conflicting containers or volumes

---

## Part 1: Rehearsal Script Execution

**Script**: `./scripts/rehearsal_containerized_deploy.sh`

### Commands Run

```bash
cd /path/to/quality-governance-platform
git log -1 --oneline  # Verify commit
./scripts/rehearsal_containerized_deploy.sh
```

### Terminal Output

```
[PASTE FULL TERMINAL OUTPUT HERE]

Expected output includes:
- Step 1: Clean up any existing containers
- Step 2: Start PostgreSQL
- Step 3: Wait for PostgreSQL to be ready
- Step 4: Run migrations
- Step 5: Start application
- Step 6: Wait for application to be ready
- Step 7: Health checks (/healthz and /readyz)
- Step 8: Smoke API tests
```

### Health Check Results

**`/healthz` Endpoint**:
```bash
curl http://localhost:8000/healthz
```

**Response**:
```json
[PASTE RESPONSE HERE]

Expected:
{
  "status": "ok",
  "request_id": "<uuid>"
}
```

**Status Code**: [e.g., 200]

---

**`/readyz` Endpoint**:
```bash
curl http://localhost:8000/readyz
```

**Response**:
```json
[PASTE RESPONSE HERE]

Expected (if DB check implemented):
{
  "status": "ready",
  "database": "connected",
  "request_id": "<uuid>"
}

OR (if DB check not yet implemented):
{
  "status": "ready",
  "request_id": "<uuid>"
}
```

**Status Code**: [e.g., 200]

---

### Migration Verification

**Command**:
```bash
docker-compose -f docker-compose.sandbox.yml exec app alembic current
```

**Output**:
```
[PASTE OUTPUT HERE]

Expected: Current migration revision (e.g., "abc123def456 (head)")
```

**Database Tables Created**:
```bash
docker-compose -f docker-compose.sandbox.yml exec postgres psql -U qgp_user -d qgp_db -c "\dt"
```

**Output**:
```
[PASTE OUTPUT HERE]

Expected tables:
- alembic_version
- users
- roles
- permissions
- policies
- incidents
- complaints
- audits
- etc.
]
```

---

### Smoke API Tests

**Test 1: RBAC Deny (403)**

**Command**:
```bash
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Policy", "content": "Test content"}'
```

**Response**:
```json
[PASTE RESPONSE HERE]

Expected:
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "...",
    "request_id": "<uuid>",
    "timestamp": "..."
  }
}
```

**Status Code**: [e.g., 403]  
**Request ID Present**: [YES/NO]

---

**Test 2: Create Policy (201)**

**Command**:
```bash
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid-token>" \
  -d '{"title": "Test Policy", "content": "Test content", "effective_date": "2026-01-01"}'
```

**Response**:
```json
[PASTE RESPONSE HERE]

Expected:
{
  "id": "<uuid>",
  "title": "Test Policy",
  "reference_number": "POL-2026-0001",
  ...
}
```

**Status Code**: [e.g., 201]  
**Audit Event Created**: [YES/NO]  
**Request ID in Audit Event**: [YES/NO]

---

**Test 3: Duplicate Policy (409)**

**Command**:
```bash
# Repeat the same POST request as Test 2
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid-token>" \
  -d '{"title": "Test Policy", "content": "Test content", "effective_date": "2026-01-01"}'
```

**Response**:
```json
[PASTE RESPONSE HERE]

Expected:
{
  "error": {
    "code": "DUPLICATE_REFERENCE_NUMBER",
    "message": "...",
    "request_id": "<uuid>",
    "timestamp": "..."
  }
}
```

**Status Code**: [e.g., 409]  
**Request ID Present**: [YES/NO]

---

### Application Logs

**Command**:
```bash
docker-compose -f docker-compose.sandbox.yml logs app | tail -50
```

**Output**:
```
[PASTE LAST 50 LINES OF APP LOGS HERE]

Look for:
- No errors during startup
- Migration success messages
- Health check requests
- API request logs with request_id
```

---

### Rehearsal Summary

**Overall Status**: [PASS/FAIL]

**Success Criteria**:
- [ ] All 8 rehearsal steps completed successfully
- [ ] PostgreSQL started and ready
- [ ] Migrations applied successfully
- [ ] Application started and healthy
- [ ] `/healthz` returns 200 OK
- [ ] `/readyz` returns 200 OK (or 503 if DB check fails)
- [ ] RBAC deny returns 403 with canonical error envelope
- [ ] Create policy returns 201 with audit event
- [ ] Duplicate policy returns 409 with canonical error envelope
- [ ] All responses include `request_id`
- [ ] No errors in application logs

**Issues Encountered**: [NONE or describe issues]

**Troubleshooting Steps Taken**: [NONE or describe steps]

---

## Part 2: Reset Drill Execution

**Script**: `./scripts/reset_drill.sh`

### Commands Run

```bash
./scripts/reset_drill.sh
```

### Terminal Output

```
[PASTE FULL TERMINAL OUTPUT HERE]

Expected output includes:
- Step 1: Stop all containers
- Step 2: Remove containers
- Step 3: Remove volumes (data loss simulation)
- Step 4: Verify clean state
- Step 5: Restart PostgreSQL
- Step 6: Run migrations (from scratch)
- Step 7: Restart application
```

### Reset Verification

**Database Tables After Reset**:
```bash
docker-compose -f docker-compose.sandbox.yml exec postgres psql -U qgp_user -d qgp_db -c "\dt"
```

**Output**:
```
[PASTE OUTPUT HERE]

Expected: Same tables as before, but empty (except alembic_version)
```

**Migration Version After Reset**:
```bash
docker-compose -f docker-compose.sandbox.yml exec app alembic current
```

**Output**:
```
[PASTE OUTPUT HERE]

Expected: Same migration revision as before reset
```

**Health Check After Reset**:
```bash
curl http://localhost:8000/healthz
```

**Response**:
```json
[PASTE RESPONSE HERE]

Expected:
{
  "status": "ok",
  "request_id": "<uuid>"
}
```

**Status Code**: [e.g., 200]

---

### Reset Drill Summary

**Overall Status**: [PASS/FAIL]

**Success Criteria**:
- [ ] All 7 reset drill steps completed successfully
- [ ] Containers stopped and removed
- [ ] Volumes removed (data loss confirmed)
- [ ] PostgreSQL restarted successfully
- [ ] Migrations applied from scratch
- [ ] Application restarted and healthy
- [ ] `/healthz` returns 200 OK after reset
- [ ] Database tables recreated correctly

**Time Taken**: [e.g., 3 minutes 45 seconds]

**Issues Encountered**: [NONE or describe issues]

**Troubleshooting Steps Taken**: [NONE or describe steps]

---

## Part 3: Cleanup

**Commands Run**:
```bash
docker-compose -f docker-compose.sandbox.yml down -v
docker system prune -f
```

**Output**:
```
[PASTE OUTPUT HERE]
```

---

## Overall Assessment

**Gate 1 Status**: [PASS/FAIL]

**Summary**:
- **Rehearsal Script**: [PASS/FAIL]
- **Reset Drill Script**: [PASS/FAIL]
- **All Success Criteria Met**: [YES/NO]

**Evidence Quality**:
- [ ] Full terminal outputs captured
- [ ] All health check responses recorded
- [ ] Smoke API test results documented
- [ ] Migration verification included
- [ ] Application logs reviewed
- [ ] No secrets exposed in outputs

**Recommendations**:
[Any recommendations for improvements or issues to address]

---

## Approval Signatures

**Executed By**: [Name/Role]  
**Date**: [YYYY-MM-DD]  
**Reviewed By**: [Name/Role]  
**Date**: [YYYY-MM-DD]  
**Approved By**: [Name/Role]  
**Date**: [YYYY-MM-DD]

---

## Appendix: Raw Logs

**If terminal outputs are too long, attach raw log files here**:
- `rehearsal_output.log` (attached)
- `reset_drill_output.log` (attached)
- `app_logs.log` (attached)
- `postgres_logs.log` (attached)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | [TO BE FILLED] | [TO BE FILLED] | Initial execution evidence |

---

**Document Status**: ⏳ TEMPLATE (awaiting execution)

**Next Steps**:
1. Execute rehearsal script on Docker-enabled host
2. Fill in all [TO BE FILLED] and [PASTE ... HERE] sections
3. Verify all success criteria are met
4. Commit this document with evidence
5. Proceed to Phase 2 (Azure staging deployment)
