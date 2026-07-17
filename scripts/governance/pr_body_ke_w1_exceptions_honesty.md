# Change Ledger (CL-PATH11-KE-W1-EXCEPTIONS-HONESTY)

## File allowlist (exclusive)
- `frontend/src/pages/KnowledgeExceptions.tsx`
- `frontend/src/pages/knowledgeExceptionsHonesty.ts` (NEW)
- `frontend/src/pages/__tests__/knowledgeExceptionsHonesty.test.ts` (NEW)
- `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx`
- `scripts/governance/pr_body_ke_w1_exceptions_honesty.md`

**Zero overlap** with forbidden paths: Actions.tsx, ComplianceAutomation*, Audits.tsx, PlanetMark.tsx, Analytics.tsx, Layout.tsx, App.tsx, client.ts, api/__init__.py, Alembic, en.json.

## 1) Summary
- **Feature / Change name:** Path11 KE-W1 — AI Exceptions honesty (identity, why, de-dupe)
- **User goal (1–2 lines):** Operators can see which standard and clause each AI proposal targets, read a specific why on hover/detail, and never review duplicate twin cards for the same entity×scheme×clause allocation.
- **In scope:** FE identity labels from isoStandards catalogue; why tooltip + expandable detail; client-side stable de-dupe; vitest proofs; Change Ledger
- **Out of scope:** DB unique constraint on scheme (KE-04 server); map-before-insert guard; Layout/App/client/Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `KnowledgeExceptions.tsx`, `knowledgeExceptionsHonesty.ts`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** Consumes existing exceptions list
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI; existing filters/URL sync unchanged
- **Tolerant reader / strict writer:** Yes — unknown scheme/clause formats fall back to raw ids with honest copy
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy:** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Each row shows human standard family (ISO 9001 vs UVDB vs Planet Mark) + clause number + catalogue title when known (KE-01, KE-02)
- [x] AC-02: Hover tooltip + expandable detail explain specific why; generic AI rationales flagged honestly (KE-03)
- [x] AC-03: Stable allocation key entity×scheme×clause; duplicate proposals collapsed with count honesty (KE-04, KE-05)
- [x] AC-04: Already confirmed/rejected allocation disables confirm/reject on twin rows
- [x] AC-05: Vitest covers helpers + page honesty describe block

## 5) Testing Evidence
- [x] `vitest run src/pages/__tests__/knowledgeExceptionsHonesty.test.ts src/pages/__tests__/KnowledgeExceptions.test.tsx`
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Operator opens inbox — sees ISO 9001 · Clause 8.5 · title, not bare `ISO9001:8.5`
- [x] **CUJ-02:** Twin proposals for same incident+clause collapse to one row with duplicate count
- [x] **CUJ-03:** Generic “possible gap” rationale shows warning + expand for full why lines

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan
- **Staging verification:** Seed duplicate proposals; confirm collapse + tooltip + already-allocated badge
- **Canary:** N/A (FE-only)
- **Prod post-deploy checks:** Spot-check Exceptions inbox row identity

## 9) Rollback Plan
- **Rollback trigger:** Inbox fails to render or hides actionable rows incorrectly
- **Rollback steps:** Revert commit, redeploy
- **Owner:** Platform team

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only; no forbidden path overlap
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary N/A
- [x] **Gate 5:** Production verification plan ready

---

# Path claim (KE-W1 exclusive)
| Path | Status |
|------|--------|
| `frontend/src/pages/KnowledgeExceptions.tsx` | **CLAIMED** |
| `frontend/src/pages/knowledgeExceptionsHonesty.ts` | **CLAIMED** |
| `frontend/src/pages/__tests__/knowledgeExceptionsHonesty.test.ts` | **CLAIMED** |
| `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx` | **CLAIMED** |
| `scripts/governance/pr_body_ke_w1_exceptions_honesty.md` | **CLAIMED** |

**FORBIDDEN (parallel PRs):** Actions.tsx, ComplianceAutomation*, Audits.tsx, PlanetMark.tsx, Analytics.tsx, Layout.tsx, App.tsx, client.ts, api/__init__.py, Alembic
