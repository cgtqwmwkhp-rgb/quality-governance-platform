# Stage 4.0 Follow-up PR - Phase 0: Scope Lock + Diff Audit

**Date**: 2026-01-05  
**Base Branch**: `main` (at SHA `7ec338b`)  
**Feature Branch**: `stage-4.0-investigation-rca-breaking`

---

## Objective

Bring governance tests and acceptance pack onto main without changing functional behavior.

---

## Candidate Commits Audit

### Commit `1da50d9` - Governance Tests
**Title**: "feat: add investigation governance tests (Phase 6)"  
**Files Changed** (3):
1. `docs/evidence/STAGE4.0_DATA_IMPACT.md` - **INCLUDE** (docs only)
2. `tests/integration/test_investigation_governance.py` - **INCLUDE** (tests only)
3. `src/api/routes/incidents.py` - **EXCLUDE** (functional code change)

**Analysis**:
- The `incidents.py` change modifies the `/incidents/{id}/investigations` endpoint return type
- Changes from `dict` to `List[InvestigationRunResponse]`
- This is a **functional change** and must be excluded from follow-up PR
- **Decision**: Extract only test file and data impact doc

### Commit `7c95505` - OpenAPI Regeneration
**Title**: "docs: update OpenAPI spec for Investigation system (Phase 7)"  
**Files Changed** (1):
1. `docs/contracts/openapi.json` - **EXCLUDE** (redundant)

**Analysis**:
- The merge commit `7ec338b` already includes an updated `openapi.json`
- This commit reduces the file size by 8 lines (formatting/whitespace)
- No correctness fix, just regeneration
- **Decision**: Exclude (redundant)

### Commit `8c35dce` - Acceptance Pack
**Title**: "docs: add Stage 4.0 acceptance pack (Phase 8)"  
**Files Changed** (1):
1. `docs/evidence/STAGE4.0_ACCEPTANCE_PACK.md` - **INCLUDE** (docs only)

**Analysis**:
- Pure documentation
- No functional changes
- **Decision**: Include

---

## Follow-up PR Scope Declaration

### ✅ Files to Include (3)

1. **`tests/integration/test_investigation_governance.py`**
   - Source: Commit `1da50d9`
   - Type: Tests
   - Purpose: 7 governance tests for Investigation system

2. **`docs/evidence/STAGE4.0_DATA_IMPACT.md`**
   - Source: Commit `1da50d9`
   - Type: Documentation
   - Purpose: Data impact statement (greenfield, zero data loss)

3. **`docs/evidence/STAGE4.0_ACCEPTANCE_PACK.md`**
   - Source: Commit `8c35dce`
   - Type: Documentation
   - Purpose: Comprehensive acceptance pack with all evidence

### ❌ Files to Exclude (2)

1. **`src/api/routes/incidents.py`**
   - Source: Commit `1da50d9`
   - Reason: Functional code change (return type modification)
   - Impact: Changes API contract for `/incidents/{id}/investigations`
   - Note: This change can be included in a separate functional PR if needed

2. **`docs/contracts/openapi.json`**
   - Source: Commit `7c95505`
   - Reason: Redundant (already updated in merge commit)
   - Impact: None (formatting/whitespace only)

---

## Gate 0: Functional Code Check

**Status**: ✅ **MET**

**Verification**:
- ✅ No functional code changes in follow-up PR scope
- ✅ Only tests and docs included
- ✅ `incidents.py` change excluded

**Excluded Functional Change**:
```python
# BEFORE (main branch):
@router.get("/{incident_id}/investigations", response_model=dict)
async def list_incident_investigations(...) -> dict:
    ...
    return {
        "items": investigations,
        "total": len(investigations),
        "page": 1,
        "page_size": len(investigations),
    }

# AFTER (excluded from follow-up):
@router.get("/{incident_id}/investigations")
async def list_incident_investigations(...):
    ...
    return [InvestigationRunResponse.model_validate(inv) for inv in investigations]
```

This change modifies the API contract and must be handled separately if needed.

---

## Strategy

**Method**: Manual file copy (not cherry-pick)

**Reason**: Cherry-picking commits would include the functional change to `incidents.py`. Instead, we'll:
1. Create new branch from main
2. Manually copy only the test and doc files
3. Update references in acceptance pack (merge SHA, CI URLs)

---

## Next Phase

**Phase 1**: Build follow-up branch + PR with selected files only.

---

**END OF PHASE 0**
