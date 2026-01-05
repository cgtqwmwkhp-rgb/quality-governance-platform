# Gate 1: Evidence Requirements Checklist

**Gate**: 1 (D0 Rehearsal Execution)  
**Status**: ⏳ PENDING EXECUTION  
**Blocker**: Docker not available in Manus sandbox  
**Action Required**: Repository owner must execute scripts on Docker-enabled host

---

## Purpose

Gate 1 requires **actual execution** of the D0 rehearsal and reset drill scripts with captured evidence. This gate must be met before proceeding to Azure staging deployment (Phase 3).

---

## Required Evidence

### 1. Execution Environment Details

- [ ] Operating System (e.g., Ubuntu 22.04, macOS 14.0, Windows 11 with WSL2)
- [ ] Docker version (e.g., Docker 24.0.7)
- [ ] Docker Compose version (e.g., Docker Compose 2.23.0)
- [ ] Git commit SHA (e.g., 749cd4c or later)
- [ ] Execution date (e.g., 2026-01-06)

### 2. Rehearsal Script Execution

- [ ] Full terminal output from `./scripts/rehearsal_containerized_deploy.sh`
- [ ] All 8 steps completed successfully
- [ ] PostgreSQL started and ready
- [ ] Migrations applied successfully
- [ ] Application started and healthy

### 3. Health Check Results

- [ ] `/healthz` endpoint response (200 OK with `request_id`)
- [ ] `/readyz` endpoint response (200 OK or 503 with `request_id`)
- [ ] Status codes recorded

### 4. Migration Verification

- [ ] Output from `alembic current` (migration revision)
- [ ] Output from `\dt` (database tables list)
- [ ] Proof that migrations were applied

### 5. Smoke API Tests

- [ ] **Test 1**: RBAC deny (403) with canonical error envelope and `request_id`
- [ ] **Test 2**: Create policy (201) with audit event and `request_id` (or SKIPPED if auth not implemented)
- [ ] **Test 3**: Duplicate policy (409) with canonical error envelope and `request_id` (or SKIPPED if auth not implemented)

### 6. Application Logs

- [ ] Last 50 lines of application logs (or full logs attached)
- [ ] No errors during startup
- [ ] Migration success messages present
- [ ] Health check requests logged
- [ ] API request logs include `request_id`

### 7. Reset Drill Execution

- [ ] Full terminal output from `./scripts/reset_drill.sh`
- [ ] All 7 steps completed successfully
- [ ] Containers stopped and removed
- [ ] Volumes removed (data loss confirmed)
- [ ] PostgreSQL restarted successfully
- [ ] Migrations applied from scratch
- [ ] Application restarted and healthy

### 8. Reset Drill Verification

- [ ] Database tables recreated correctly (output from `\dt`)
- [ ] Migration version matches pre-reset version (output from `alembic current`)
- [ ] `/healthz` returns 200 OK after reset
- [ ] Time taken for reset drill (e.g., 3m 45s)

### 9. Cleanup

- [ ] Output from `docker compose down -v`
- [ ] Output from `docker system prune -f`

### 10. Evidence Quality

- [ ] All [TO BE FILLED] sections filled in addendum template
- [ ] All [PASTE ... HERE] sections have content
- [ ] No secrets exposed in outputs (database passwords, API keys, etc.)
- [ ] Approval signatures filled (or marked as pending)
- [ ] Overall assessment completed (PASS/FAIL)

---

## How to Provide Evidence

### Step 1: Execute Scripts

Follow the step-by-step guide in `docs/runbooks/D0_REHEARSAL_RUNBOOK.md`:

```bash
cd /path/to/quality-governance-platform
./scripts/rehearsal_containerized_deploy.sh 2>&1 | tee rehearsal_output.log
./scripts/reset_drill.sh 2>&1 | tee reset_drill_output.log
```

### Step 2: Fill Evidence Template

Open `docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md` and fill in all sections:
- Part 1: Rehearsal Script Execution
- Part 2: Reset Drill Execution
- Part 3: Cleanup
- Overall Assessment

### Step 3: Commit Evidence

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

## Success Criteria

**Gate 1 is met when**:
- ✅ All required evidence sections are filled
- ✅ Rehearsal script completed successfully (all 8 steps)
- ✅ Reset drill completed successfully (all 7 steps)
- ✅ Health checks return expected responses
- ✅ Smoke API tests pass (or skipped with justification)
- ✅ Migrations verified
- ✅ Application logs reviewed (no errors)
- ✅ No secrets exposed
- ✅ Evidence committed to repository

**Gate 1 is NOT met when**:
- ❌ Evidence template is still empty or incomplete
- ❌ Scripts were not executed (only documented)
- ❌ Any step failed without resolution
- ❌ Secrets are exposed in outputs
- ❌ Evidence is not committed to repository

---

## Troubleshooting

If you encounter issues during execution, see the troubleshooting section in `docs/runbooks/D0_REHEARSAL_RUNBOOK.md`.

Common issues:
- Docker not running
- Port 8000 already in use
- PostgreSQL fails to start
- Migrations fail
- Health check returns 503
- API tests return 500 errors
- Authentication not implemented (skip Tests 2 and 3)

---

## Timeline

**Estimated Time**: 15-20 minutes total
- Rehearsal script: ~3-5 minutes
- Reset drill: ~3-5 minutes
- Evidence capture: ~5-10 minutes

---

## Blocker Status

**Current Status**: ⏳ PENDING EXECUTION

**Reason**: Docker is not available in the Manus sandbox environment. Rehearsal and reset drill scripts require Docker to execute.

**Action Required**: Repository owner must execute scripts on a Docker-enabled host (local machine, CI runner, or cloud VM).

**Next Steps After Gate 1**:
1. ✅ Gate 1 evidence committed
2. ➡️ Phase 2: Azure staging prerequisites
3. ➡️ Phase 3: Execute Azure staging deployment
4. ➡️ Phase 4: Post-deploy verification
5. ➡️ Phase 5: Staging rollback drill
6. ➡️ Phase 6: Acceptance packs and sign-offs
7. ➡️ Phase 7: D3 promotion guardrails

---

## References

- **Evidence Template**: `docs/evidence/STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md`
- **Execution Runbook**: `docs/runbooks/D0_REHEARSAL_RUNBOOK.md`
- **Rehearsal Script**: `scripts/rehearsal_containerized_deploy.sh`
- **Reset Drill Script**: `scripts/reset_drill.sh`
- **Completion Summary**: `docs/evidence/STAGES_D0_D1_COMPLETION_SUMMARY.md`

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-05  
**Maintained By**: Platform Team
