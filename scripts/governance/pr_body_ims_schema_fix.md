# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** IMS schema — create `ims_requirements` and `cross_standard_mappings` when missing
- **User goal (1-2 lines):** Fix production `ProgrammingError` / 500 on ISO Compliance and cross-standard mapping APIs when databases were migrated without CREATE TABLE for these ORM-backed tables.
- **In scope:** Alembic migration `20260407_create_ims_requirements_and_cross_standard_mappings.py`, defensive GET handlers in `cross_standard_mappings.py`
- **Out of scope:** Seeding mappings, UI copy changes
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** `src/api/routes/cross_standard_mappings.py`
- **Database:** New revision `f6e5d4c3b2a1` (revises `e4f5a6b7c8d9`)
- **APIs:** Behaviour only — GET list/standards return empty on SQL failure instead of 500 when schema missing
- **Workflows:** None

## 3) Compatibility & Data Safety
- **Strategy:** Additive — `CREATE TABLE IF NOT EXISTS` via existence check
- **Breaking changes:** None
- **Rollback:** Downgrade drops tables (risky if populated); prefer forward fix

## 4) Acceptance Criteria (AC)
- [x] AC-01: Migration filename passes `scripts/validate_migration_naming.py`
- [x] AC-02: `flake8` clean on touched Python
- [x] AC-03: `tests/unit/test_wave2_cross_standard_integration.py` and `test_wave2_compliance_spine.py` pass
- [x] AC-04: `make pr-ready` passes

## 5) Testing Evidence (link to runs)
- [x] Local: `make pr-ready`, unit tests above
- [x] CI: Linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Cross-standard route mounted; list endpoint tolerates DB errors
- [x] CUJ-02: Compliance canonical enrichment can query `ims_requirements` after migration
- [x] CUJ-03: Fresh DB `alembic upgrade head` creates IMS tables when missing

## 7) Observability & Ops
- **Logs:** Warning log on cross-standard read SQL failures

## 8) Release Plan
- Merge → deploy → **run `alembic upgrade head` on prod** before expecting UI recovery

## 9) Rollback Plan
- Revert PR; do not downgrade prod if tables contain data

## 10) Evidence Pack
- CI run URL after merge

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Change Ledger complete
- [x] **Gate 1:** Schema change reviewed
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification after deploy
- [ ] **Gate 4:** N/A
- [x] **Gate 5:** Prod migration step documented above
