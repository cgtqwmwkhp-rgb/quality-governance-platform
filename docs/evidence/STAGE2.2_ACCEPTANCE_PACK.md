# Stage 2.2 Acceptance Pack: Incidents Module (Governed Delivery)

## Goal
Implement the Incidents module (minimal CRUD) and align Policy Library delete semantics, demonstrating the full governed feature delivery pattern.

## Acceptance Criteria
1.  **Policy Alignment**: Policy Library delete semantics are clarified and verified as **Hard Delete**.
2.  **Schema Discipline**: Incidents model is integrated, and no schema drift is detected.
3.  **API Implementation**: Incidents API (POST, GET, LIST, PATCH) is functional and deterministic.
4.  **Test Coverage**: Unit and Postgres-backed integration tests are implemented and pass.
5.  **CI Gates**: All CI checks (Code Quality, Security, Governance) pass on the final commit.
6.  **Documentation**: Module documentation is created.

## Evidence Summary

| Phase | Deliverable | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **0** | Policy Delete Semantics Alignment | ✅ PASS | `tests/integration/test_policy_api.py` updated to verify hard delete. |
| **1** | Incidents Model + Migration | ✅ PASS | Model exists, `alembic check` is clean. No new migration needed. |
| **2** | Incidents API (Minimal, Deterministic) | ✅ PASS | `src/api/routes/incidents.py` implemented with deterministic ordering. |
| **3** | Tests (Unit + Integration) | ✅ PASS | 9 Unit Tests + 5 Integration Tests pass (Total 14 new tests). |
| **4** | Governance + Security Verification | ✅ PASS | All CI checks passed on final commit `41b07ce`. |
| **5** | Docs + Acceptance Pack | ✅ PASS | `docs/modules/INCIDENTS.md` created. |

## CI Evidence (Final Commit: 41b07ce)
- **PR:** #10
- **Status:** All Checks Passed
- **Key Gate Statuses:**
    - Code Quality: **SUCCESS**
    - Unit Tests: **SUCCESS** (14 new tests included)
    - Integration Tests: **SUCCESS** (Postgres-backed)
    - Security Scan: **SUCCESS**
    - CI Security Covenant: **SUCCESS**

## Rollout Notes

1.  **Deployment**: Standard CI/CD process (PR merge to main).
2.  **Migration**: No new migration required for this stage.
3.  **Verification**: Verify API endpoints:
    - `POST /api/v1/incidents` (Check `reference_number` generation)
    - `GET /api/v1/incidents?page=1&page_size=10` (Check deterministic ordering)
    - `DELETE /api/v1/policies/{id}` (Verify hard delete behavior)

## Rollback Notes

1.  **Rollback Strategy**: Standard Git revert of PR #10.
2.  **Data Impact**: Low. The Incidents module is new, so reverting the code will only remove the API functionality. No database schema changes were introduced.
3.  **Policy Impact**: Reverting the code will not affect the Policy Library delete semantics, as the change was only in the test/documentation. The underlying hard delete behavior remains.
