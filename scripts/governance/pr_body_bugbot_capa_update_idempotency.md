# Change Ledger (CL-BUGBOT-CAPA-UPDATE-IDEM)

## File allowlist (exclusive)
- `src/api/routes/actions.py`
- `src/domain/services/capa_service.py`
- `tests/unit/test_capa_source_investigation.py`
- `scripts/governance/pr_body_bugbot_capa_update_idempotency.md`

**Zero overlap** with Layout/App/client.ts/api/__init__.py/Alembic/InvestigationDetail.

## 1) Summary
- **Feature / Change name:** Bugbot Autofix — investigation CAPA update routing + untitled idempotency
- **User goal (1–2 lines):** Status updates on investigation-linked formal CAPAs succeed via unified Actions API; untitled convenience creates do not crash when multiple CAPAs already exist.
- **In scope:** `update_action` CAPA fallback for `source_type=investigation`; `create_capa_for_investigation` prior lookup `.limit(1)`; unit coverage
- **Out of scope:** InvestigationDetail FE rewrite; physical single-actions-table migration
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** `actions.py` update path; `capa_service.py` untitled create lookup
- **APIs:** `PATCH /api/v1/actions/{id}` with `source_type=investigation` can resolve CAPAAction rows
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive lookup fallback
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: When `source_type=investigation` and no InvestigationAction row exists, update loads CAPAAction by id+tenant
- [x] AC-02: Untitled `create_capa_for_investigation` uses `.limit(1)` so multiple existing CAPAs do not raise
- [x] AC-03: Existing titled-create always-insert behavior preserved
- [x] AC-04: Unit tests cover untitled idempotency path

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_capa_source_investigation.py`
- [ ] CI — linked after PR

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Investigation CAPA status update via Actions API succeeds for formal CAPA rows
- [x] **CUJ-02:** Untitled convenience create with multiple existing CAPAs returns one without MultipleResultsFound
- [x] **CUJ-03:** Titled create still inserts a new CAPA

## 7) Observability & Ops
- **Logs:** Existing
- **Metrics:** Existing
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Create two titled CAPAs on one investigation; change status on each via Actions
- **Canary plan:** Full promote after tip serial
- **Prod post-deploy checks:** Spot-check Investigation CAPA status change

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CAPA updates fail or duplicate untitled creates regress
- **Rollback steps:** Revert commit and redeploy
- **Owner:** Overnight tip LIVE owner / Platform ops

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: pending
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Prod post-deploy checks complete
