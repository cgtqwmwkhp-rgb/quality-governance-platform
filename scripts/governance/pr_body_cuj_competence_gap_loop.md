# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Assessor competence_gap → Workforce closed loop (R1 auditor CUJ)
- **User goal (1–2 lines):** When Assessor Exceptions confirm a competence_gap / nonconformity signal, open an idempotent workforce gap action that can create CAPA and prove resolve via golden-thread evidence.
- **In scope:** `competence_gap_actions` table + service + `/api/v1/workforce/competence-gaps/*`; `CAPASource.competence_gap`; Assessor Exceptions confirm hook; FE inbox `CompetenceGaps.tsx`; golden-thread GET; unit/integration tests; Change Ledger
- **Out of scope:** TrainingTicket migration (owned by `path11/workforce-p0-spine`); Layout / Admin hub; SWA; portal Field Work Inbox; IMMU audit_service bridge; Supervisor Intake Triage; GKB WL1/WL2 audit-pack surfaces
- **Feature flag / kill switch:** None — additive table/endpoints; confirm hook is best-effort (confirm still succeeds if gap create fails)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `CompetenceGaps.tsx` inbox; `competenceGapClient.ts`; App route `/workforce/competence-gaps` (no Layout nav rewrite); i18n `competenceGaps.*`
- **Backend (handlers/services):** `competence_gap_service.py`; `workforce_competence_gaps.py`; Assessor confirm/bulk-confirm hook in `governed_knowledge.py`; `CAPASource.competence_gap`; unified Actions source allowlist
- **APIs (endpoints changed/added):** `POST /from-signal`; `GET /`; `GET /{id}`; `POST /{id}/link`; `POST /{id}/create-capa`; `POST /{id}/resolve`; `GET /{id}/golden-thread`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Competence gap serialize + CAPA action serialize; confirm response may include `competence_gap_id` / `competence_gap_href`
- **Database (migrations/entities/indexes):** `20260714_competence_gap_loop` — table + capasource enum value; FK to `competency_requirements` (preferred); **no** `training_tickets` rewrite
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive enum value + new table; ticket resolve path nullable until P0 TrainingTicket lands
- **Tolerant reader / strict writer applied?** Yes — resolve prefers `requirement_id` + active `CompetencyRecord`; ticket_scheme soft-probes TrainingTicket only if model exists
- **Breaking changes:** None
- **Migration plan:** Alembic `20260714_comp_gap` after `20260713_op_assess`
- **Rollback strategy (DB):** Drop `competence_gap_actions`; enum value `competence_gap` irreversible on Postgres (safe leftover)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Confirming Assessor signal `competence_gap` / `nonconformity` / `gap` creates exactly one `competence_gap_actions` row (retry idempotent)
- [x] AC-02: Create CAPA writes `source_type=competence_gap`, `source_id=gap.id`, with owner/due
- [x] AC-03: Resolve blocked unless linked engineer has active `CompetencyRecord` for requirement (or verified TrainingTicket when P0 spine present)
- [x] AC-04: `GET …/golden-thread` returns ordered events with actors/timestamps — no invented SMTP
- [x] AC-05: Coverage/SoA policy untouched (NC/gap still excluded from conformance)
- [x] AC-06: Exclusive allowlist respected — no TrainingTicket migration rewrite; no Layout/SWA/portal/IMMU/ops triage

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_competence_gap_service.py`
- [x] Integration — `tests/integration/test_competence_gap_cuj.py`
- [x] FE — `frontend/src/pages/__tests__/CompetenceGaps.test.tsx`
- [ ] Full CI — linked after PR checks
- [ ] Staging smoke — deferred to Gate 3

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Assessor Exceptions confirm NC/gap → idempotent competence_gap_actions row
- [x] CUJ-02: HSEQ opens Competence Gaps inbox → Create CAPA → visible with owner/due (`competence_gap` source)
- [x] CUJ-03: Link engineer + requirement → Resolve requires active CompetencyRecord → golden-thread pack

## 7) Observability & Ops
- **Logs:** Service logger + `AiDecisionLog` + `record_audit_event` payloads for detect/link/capa/resolve
- **Metrics:** Existing CAPA metrics unchanged
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm Assessor NC → gap row; Create CAPA; golden-thread GET; resolve with active competency record
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** `/api/v1/meta/version` SHA; smoke from-signal idempotent + create-capa

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Spurious mass gap creation; create-capa 5xx; resolve incorrectly closing unrelated CAPA
- **Rollback steps:** Revert app deploy; leave additive table/enum; stop using competence-gaps endpoints
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main`
- Staging deploy evidence: pending
- Parallel note: coordinates with `path11/workforce-p0-spine` (requirement_id first; ticket resolve nullable)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
