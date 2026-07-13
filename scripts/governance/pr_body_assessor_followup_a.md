# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Assessor Follow-up A — lifecycle hooks + coverage honesty
- **User goal (1–2 lines):** Auto-assess complaints, near misses, RTAs, and audit findings on create/update (same fire-and-forget pattern as incidents), surface Standards on audit findings, and stop NC/gap/opportunity signals from inflating IMS/compliance coverage %.
- **In scope:** Backend auto-assess hooks; audit finding Standards panel; coverage_percentage filtering by signal_type; unit tests; Change Ledger
- **Out of scope:** Recurrence clustering; PagerDuty; rewriting #922 CI fixer / isort on `test_governed_knowledge_service.py`
- **Feature flag / kill switch:** None (hooks never fail the parent save; coverage filter is additive honesty)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Audits` findings view — Standards button + `StandardsAssessmentPanel` on deep-linked finding detail (`?view=findings&findingId=`)
- **Backend (handlers/services):** Auto-assess hooks on complaint / near_miss / RTA / audit finding create+update; `counts_toward_compliance_coverage` + `calculate_compliance_coverage` signal filter; IMS dashboard + compliance route pass `signal_type`
- **APIs (endpoints changed/added):** None new — hooks on existing create/update routes
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `EvidenceLink.signal_type` optional field for coverage calc
- **Database (migrations/entities/indexes):** None (uses `signal_type` from #922 / `20260713_op_assess`)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive / stacked on `path11/operational-standards-assessor`
- **Tolerant reader / strict writer applied?** Yes — legacy CEL rows with null `signal_type` still count as evidence; only explicit NC/gap/opportunity are excluded from %
- **Breaking changes:** None (coverage % may drop where operational signals previously inflated it — intentional honesty)
- **Migration plan:** Depends on #922 migration `20260713_op_assess` for `signal_type` column
- **Rollback strategy (DB):** Revert app; no new migration

## 4) Acceptance Criteria (AC)
- [x] AC-01: Complaint create/update triggers assess without failing save
- [x] AC-02: Near miss create/update triggers assess without failing save
- [x] AC-03: RTA create/update triggers assess without failing save
- [x] AC-04: Audit finding create/update triggers assess (passes finding_type) without failing save
- [x] AC-05: Audit finding deep-link detail mounts StandardsAssessmentPanel
- [x] AC-06: `signal_type=nonconformity|gap|opportunity` does not increase `coverage_percentage`; evidence/null still counts
- [x] AC-07: Unit tests cover hooks + coverage honesty

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_coverage_signal_honesty.py` + `tests/unit/test_assessor_followup_hooks.py` (14 passed locally)
- [x] Related regression — wave2 compliance spine / IMS tenant-safe / iso_compliance unit (local)
- [ ] Integration / E2E — deferred to CI + staging after #922 merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create/update complaint|near_miss|RTA|finding does not fail if assess throws
- [x] CUJ-02: Operator opens finding via `?findingId=` → Standards panel available
- [x] CUJ-03: Adding NC-linked CEL does not raise coverage % vs empty / evidence-only baseline

## 7) Observability & Ops
- **Logs:** Warning logs on assess hook failure (per entity type); existing `operational_standards_assess` AI decision log
- **Metrics:** Existing knowledge-bank / readiness
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Merge after #922; migrate if needed; create one complaint + one finding; confirm Exceptions + coverage unchanged by NC-only links
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** `/api/v1/meta/version` SHA; smoke create complaint assess; IMS coverage sanity

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Assess 5xx flood; coverage % collapse unexpected for evidence-only tenants; hook regressions on save
- **Rollback steps:** Revert this PR deploy; leave #922 column; optional hotfix no-op hooks
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `path11/operational-standards-assessor` (PR #922)
- Staging deploy evidence: pending after #922 + this merge

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Stacking note
Blocked on **PR #922** (`path11/operational-standards-assessor`) merge for: `signal_type` migration, assess API, `StandardsAssessmentPanel`, and `governed_knowledge_service.assess_operational_entity`.
