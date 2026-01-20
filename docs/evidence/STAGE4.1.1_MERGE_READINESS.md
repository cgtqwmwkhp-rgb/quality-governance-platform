# Stage 4.1.1: Merge Readiness Checklist + Post-Merge Smoke Plan

**Date**: 2026-01-07  
**PR**: [#28](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/28)  
**Final Commit**: `aa0ce71`  
**CI Run**: [20776451981](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/20776451981)

---

## 1. Merge Readiness Checklist

### Pre-Merge Verification

- [ ] **CI Status**: All 8/8 quality gates GREEN
  - [x] ADR-0002 Fail-Fast Proof
  - [x] All Checks Passed
  - [x] Build Check
  - [x] CI Security Covenant
  - [x] Code Quality
  - [x] Integration Tests
  - [x] Security Scan
  - [x] Unit Tests

- [ ] **PR Approval**: At least one approval from project maintainer

- [ ] **Documentation**: Acceptance pack and merge readiness docs complete
  - [x] `docs/evidence/STAGE4.1.1_ACCEPTANCE_PACK.md`
  - [x] `docs/evidence/STAGE4.1.1_MERGE_READINESS.md` (this file)
  - [x] `docs/openapi_stage4.1.1.json`

- [ ] **Breaking Changes**: None (backward-compatible pagination)

- [ ] **Migration**: None required (no schema changes)

### Merge Execution

- [ ] **Merge Strategy**: Squash merge (single commit to main)
- [ ] **Merge Message**: Use PR title + body summary
- [ ] **Post-Merge**: Execute smoke plan immediately

---

## 2. Post-Merge Smoke Plan

### Objective

Verify that the paginated investigation linkage endpoints work correctly on the main branch after merge.

### Scope

Test all 3 linkage endpoints:
- `GET /api/v1/incidents/{incident_id}/investigations`
- `GET /api/v1/rtas/{rta_id}/investigations`
- `GET /api/v1/complaints/{complaint_id}/investigations`

### Test Cases

#### 2.1 Default Pagination (page=1, page_size=25)

**Endpoint**: `GET /api/v1/incidents/{incident_id}/investigations`

**Expected**:
```json
{
  "items": [...],
  "page": 1,
  "page_size": 25,
  "total": <count>,
  "total_pages": <ceil(total/25)>
}
```

**Verification**:
- [ ] Response has all 5 fields (`items`, `page`, `page_size`, `total`, `total_pages`)
- [ ] `page` = 1
- [ ] `page_size` = 25
- [ ] `total_pages` = ceil(total / 25)

#### 2.2 Custom Page Size

**Endpoint**: `GET /api/v1/rtas/{rta_id}/investigations?page_size=10`

**Expected**:
```json
{
  "items": [...],
  "page": 1,
  "page_size": 10,
  "total": <count>,
  "total_pages": <ceil(total/10)>
}
```

**Verification**:
- [ ] `page_size` = 10
- [ ] `total_pages` = ceil(total / 10)

#### 2.3 Deterministic Ordering

**Endpoint**: `GET /api/v1/complaints/{complaint_id}/investigations`

**Expected**: Items ordered by `created_at DESC, id ASC`

**Verification**:
- [ ] Call endpoint twice
- [ ] Verify both responses return items in the same order
- [ ] Verify first item has the latest `created_at`

#### 2.4 Invalid Query Parameters (422 Validation)

**Endpoint**: `GET /api/v1/incidents/{incident_id}/investigations?page=0`

**Expected**: 422 Unprocessable Entity

**Verification**:
- [ ] `page=0` returns 422
- [ ] `page=-1` returns 422
- [ ] `page_size=0` returns 422
- [ ] `page_size=101` returns 422

#### 2.5 Nonexistent Entity (404)

**Endpoint**: `GET /api/v1/incidents/999999/investigations`

**Expected**: 404 Not Found

**Verification**:
- [ ] Returns 404 for nonexistent incident ID

---

## 3. Smoke Test Execution

### Option A: Manual (curl)

```bash
# Set variables
BASE_URL="http://localhost:8000"  # or staging URL
TOKEN="<auth_token>"
INCIDENT_ID="<valid_incident_id>"

# Test 1: Default pagination
curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/incidents/$INCIDENT_ID/investigations"

# Test 2: Custom page_size
curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/incidents/$INCIDENT_ID/investigations?page_size=10"

# Test 3: Invalid page (expect 422)
curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/incidents/$INCIDENT_ID/investigations?page=0"

# Test 4: Nonexistent entity (expect 404)
curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/incidents/999999/investigations"
```

### Option B: Automated (pytest)

```bash
# Run specific smoke tests
pytest tests/integration/test_investigation_governance.py::TestInvestigationGovernance::test_incident_investigations_pagination_fields -v
pytest tests/integration/test_rta_governance.py::test_rta_investigations_pagination_fields -v
pytest tests/integration/test_rta_governance.py::test_complaint_investigations_pagination_fields -v
```

---

## 4. Success Criteria

- [ ] All 5 test cases pass
- [ ] No errors in application logs
- [ ] Response times < 500ms for typical queries

---

## 5. Rollback Plan (if smoke fails)

1. **Immediate**: Revert merge commit on main
   ```bash
   git revert <merge_commit_sha> -m 1
   git push origin main
   ```

2. **Investigation**: Analyze failure logs and root cause

3. **Fix**: Create new PR with fix

4. **Re-test**: Run full CI + smoke plan again

---

## 6. Next Steps After Successful Smoke

Proceed to **Stage 4.1.1 Deployment Execution** (see separate deployment plan).
