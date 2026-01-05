# Stage 4.0.1 Phase 0: Scope Lock + Baseline

**Date**: 2026-01-05  
**Task**: Close Stage 4.0 properly with follow-up PR, RBAC completeness, and contract stabilization

---

## Baseline: Main vs Follow-up Branch

### On Main Already (commit 7ec338b)
| Component | Status |
|-----------|--------|
| Investigation models | ✅ Merged |
| Investigation Template API (5 endpoints) | ✅ Merged |
| Investigation Run API (4 endpoints) | ✅ Merged |
| Database migrations (2) | ✅ Merged |
| Breaking change (remove /api/v1/rtas) | ✅ Merged |
| OpenAPI spec update | ✅ Merged |
| Health endpoints (/healthz, /readyz) | ✅ Merged |
| Core evidence docs | ✅ Merged |

### On Follow-up Branch Only (PR #25)
| File | Type | Size | Purpose |
|------|------|------|---------|
| `tests/integration/test_investigation_governance.py` | Test | 8.9KB | 7 governance tests (RBAC, determinism, pagination, linkage) |
| `docs/evidence/STAGE4.0_DATA_IMPACT.md` | Doc | 3.4KB | Data impact statement (greenfield) |
| `docs/evidence/STAGE4.0_ACCEPTANCE_PACK.md` | Doc | 16KB | Complete acceptance pack (all 8 phases) |
| `docs/evidence/STAGE4.0_FOLLOWUP_PHASE0_SCOPE.md` | Doc | 2.8KB | Scope audit for follow-up |
| `src/api/routes/incidents.py` | Code | 6 lines | **Bug fix**: serialization (return schemas not raw objects) |

---

## Scope Analysis

### Follow-up PR #25 Scope
**Intended**: Tests + docs only  
**Actual**: Tests + docs + **1 minimal bug fix** (incidents.py serialization)

**Bug Fix Justification**:
- The `/incidents/{id}/investigations` endpoint in main returns raw SQLAlchemy objects
- This causes `PydanticSerializationError` when called
- Fix is 6 lines: import schema + serialize objects before return
- Without this fix, the endpoint is broken and governance tests cannot pass

**Scope Verdict**: ✅ ACCEPTABLE (minimal bug fix to enable tests)

---

## RBAC Permissions to Implement (Phase 2)

### Current State
- Investigation endpoints require authentication (`current_user: CurrentUser`)
- No fine-grained permissions implemented
- Only 401 (unauthenticated) path exists
- No 403 (forbidden) path exists

### Minimal RBAC Permissions
| Permission | Endpoint | Method | Description |
|------------|----------|--------|-------------|
| `investigation_template:create` | `/api/v1/investigation-templates/` | POST | Create template |
| `investigation_template:read` | `/api/v1/investigation-templates/` | GET | List templates |
| `investigation_template:read` | `/api/v1/investigation-templates/{id}` | GET | Get template |
| `investigation_template:update` | `/api/v1/investigation-templates/{id}` | PATCH | Update template |
| `investigation_template:delete` | `/api/v1/investigation-templates/{id}` | DELETE | Delete template |
| `investigation:create` | `/api/v1/investigations/` | POST | Create investigation |
| `investigation:read` | `/api/v1/investigations/` | GET | List investigations |
| `investigation:read` | `/api/v1/investigations/{id}` | GET | Get investigation |
| `investigation:update` | `/api/v1/investigations/{id}` | PATCH | Update investigation |

---

## Incidents Linkage Contract Issue (Phase 3)

### Current Tension
The `/incidents/{id}/investigations` endpoint has inconsistent contract:

**In main (7ec338b)**: Returns dict with pagination
```json
{
  "items": [...],
  "total": 5,
  "page": 1,
  "page_size": 5
}
```

**In PR #25 (8c50dad)**: Returns list
```json
[...]
```

### Decision Required
**Option A** (preferred): Paginated envelope (consistent with other list endpoints)
**Option B**: Simple list (simpler but inconsistent)

**Recommendation**: Option A (paginated envelope) for consistency

---

## Gate 0 Status

**Scope Check**:
- ✅ No UI work
- ✅ No new modules
- ✅ Tests + docs + minimal bug fix only

**GATE 0**: ✅ MET

---

## Next Steps

1. **Phase 1**: Merge PR #25 (tests + docs + bug fix)
2. **Phase 2**: Implement RBAC permissions + 403 tests
3. **Phase 3**: Stabilize incidents linkage contract (paginated envelope)
4. **Phase 4**: Regenerate OpenAPI + verify drift/invariants
5. **Phase 5**: Create Stage 4.0.1 acceptance pack

---

**Status**: Ready to proceed to Phase 1
