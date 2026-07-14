# Change Ledger (CL-WORKFORCE-P0-SPINE)

## 1) Summary
- **Feature / Change name:** Workforce Northern Star P0 — Competence Graph Spine (TrainingTicket + Requirements + Gate wiring)
- **User goal (1–2 lines):** Make competence data truthful before any matrix/passport UI: first-class tickets, requirement frequency, tenant fail-closed, and competency gate on assessment/induction start (soft→hard).
- **In scope:** TrainingTicket entity + migration; CompetencyRequirement CRUD/allocate + reassessment_interval_days; fail-safe tenant_id NOT NULL on engineers/competency_records/competency_requirements; wire gate into start endpoints; ticket + requirement APIs; unit tests; Change Ledger
- **Out of scope:** Matrix dashboard UI; QR passport UI; GKB compliance audit-pack; nav Layout admin hub; SWA; portal work inbox; complaints; scheme API verify hooks; Celery expiry alerts
- **Feature flag / kill switch:** `COMPETENCY_GATE_MODE=soft|hard` (default soft)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (API-first overnight; no supervisor dashboard)
- **Backend (handlers/services):** `workforce_spine` helpers; assessment/induction start+complete; engineer tenant require; new ticket/requirement routes
- **APIs (endpoints changed/added):**
  - `GET/POST/PATCH/DELETE /api/v1/training-tickets`
  - `GET/POST/PATCH/DELETE /api/v1/competency-requirements` + `POST .../{id}/allocate`
  - `POST /api/v1/assessments/{id}/start` and inductions start — competency gate soft-warn / hard-block
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Engineer schemas extended; Assessment/Induction start response optional gate fields
- **Database (migrations/entities/indexes):** `20260713_wf_p0_spine` (training_tickets + requirement role_key/site + certifications_json backfill); `20260713_wf_tenant_nn` (fail-safe NOT NULL)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** `COMPETENCY_GATE_MODE` (default `soft`)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive APIs; start responses gain optional gate fields (tolerant readers)
- **Tolerant reader / strict writer applied?** Yes — soft mode default; hard mode opt-in via env
- **Breaking changes:** Engineer/competency ORM `tenant_id` now required; create paths fail closed without tenant membership
- **Migration plan:** Backfill engineers←users.tenant_id; records←engineers.tenant_id; never invent tenant_id=1; SET NOT NULL only when remaining nulls=0
- **Rollback strategy (DB):** Downgrade restores nullable tenant_id; drop training_tickets table

## 4) Acceptance Criteria (AC)
- [x] AC-01: TrainingTicket first-class entity with scheme, number, expiry, verify_state, evidence FK, tenant_id NOT NULL
- [x] AC-02: CompetencyRequirement CRUD + allocate; reassessment_interval_days used on assessment/induction complete (no 365 hardcode)
- [x] AC-03: Fail-safe tenant_id NOT NULL migration for engineers / competency_records / competency_requirements
- [x] AC-04: Competency gate wired into assessment/induction START (soft-warn → hard-block via COMPETENCY_GATE_MODE)
- [x] AC-05: Minimal ticket + requirement APIs with unit tests; no matrix/passport FE overnight
- [x] AC-06: Exclusive allowlist respected (no GKB / nav Layout / SWA / portal inbox / complaints)

## 5) Testing Evidence (link to runs)
- [x] Lint — black/isort on touched files
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_workforce_p0_spine.py` + competency gate + engineer auth (26 passed locally)
- [ ] Integration tests — CI after open
- [ ] Contract tests (if applicable) — N/A overnight (OpenAPI baseline not refreshed in this PR)
- [ ] E2E Smoke — N/A for spine API-only overnight

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Soft gate allows assessment start with warning fields when competence not cleared
- [x] CUJ-02: Hard gate raises COMPETENCY_GATE_BLOCKED and does not start
- [x] CUJ-03: Expiry interval resolves from CompetencyRequirement.reassessment_interval_days (not hardcoded 365)
- [x] CUJ-04: TrainingTicket ORM requires tenant_id; migration fail-safe never invents tenant_id=1

## 7) Observability & Ops
- **Logs:** Migration fail-safe warnings when residual NULLs remain
- **Metrics:** None new
- **Alerts:** None new (expiry orchestration is P2)
- **Runbook updates:** Inventory + baseline shrunk for workforce spine tables; `.env.example` documents COMPETENCY_GATE_MODE

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Apply migrations; create ticket via API; start assessment with soft mode and confirm warning fields; flip hard mode and confirm 403
- **Canary plan:** N/A — keep COMPETENCY_GATE_MODE=soft until ops ready
- **Prod post-deploy checks:** Confirm training_tickets table exists; NULL counts on engineers/competency_* after backfill; soft gate default

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration fail-safe noise blocking deploy, or start endpoints regressing supervisor CUJ
- **Rollback steps:** Revert PR; set COMPETENCY_GATE_MODE=soft; downgrade `20260713_wf_tenant_nn` then `20260713_wf_p0_spine` if needed
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft overnight — no merge)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved for P0 spine (API-first; FE deferred)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — N/A soft default
- [x] **Gate 5:** Production verification plan + monitoring ready — soft default; hard mode opt-in
