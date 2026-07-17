# Change Ledger (CL-PATH11-INV-CAPA-STITCH-W1)

## File allowlist (exclusive)
- `frontend/src/api/investigationsClient.ts`
- `frontend/src/components/investigations/handoffLinks.ts`
- `frontend/src/components/investigations/handoffLinks.test.ts`
- `frontend/src/pages/Actions.tsx`
- `frontend/src/pages/__tests__/Actions.test.tsx`
- `frontend/src/pages/InvestigationDetail.tsx`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx`
- `frontend/src/pages/investigation/InvestigationActions.tsx`
- `src/api/routes/_action_unified.py`
- `src/domain/services/capa_service.py`
- `tests/unit/test_capa_source_investigation.py`
- `tests/unit/test_regulatory_watch_actions.py`
- `scripts/governance/pr_body_inv_capa_stitch.md`

**Zero overlap** with tip OCR (#1108) / HSG245 (#1111) migration paths; no Alembic.

## 1) Summary
- **Feature / Change name:** Investigation → CAPA 360 stitch (Wave 1)
- **User goal (1–2 lines):** From an investigation, create a CAPA in few clicks with a mandated parent link (no typing Source ID); CAPA appears in the investigation bucket and the central Actions list. API 404s show the real detail (e.g. Incident not found), not a rewritten “Action not found.”
- **In scope:** Honest Actions 404 mapping; in-context CAPA create via `POST /investigations/{id}/capa`; create deep-link lock for investigation parent; include investigation `CAPAAction` in unified Actions filter; FE/BE unit tests
- **Out of scope:** Physical single-actions-table migration; full CAPA workflow redesign; audit/finding create parity
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend:** InvestigationDetail CAPA CTA opens Actions tab create dialog; InvestigationActions locked parent badge; Actions modal locks investigation parent + calls `investigationsApi.createCapa`; handoffLinks create/returnTo; honest classifyError
- **Backend:** `investigation` added to `CAPA_ONLY_API_SOURCE_TYPES`; titled CAPA creates always insert (idempotent only when title omitted)
- **APIs:** Consumes existing `POST /api/v1/investigations/{id}/capa`; list filter includes CAPA rows for `source_type=investigation`
- **Schemas/contracts:** None
- **Database:** None (no Alembic)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX + filter inclusion; multi-table storage unchanged
- **Tolerant reader / strict writer applied?** Yes — preserve API error detail on 404
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Actions create/list 404 surfaces API detail (not blanket “Action not found”)
- [x] AC-02: Investigation Create CAPA CTA opens in-detail create (parent locked; no Source ID)
- [x] AC-03: In-detail create calls `POST /investigations/{id}/capa`
- [x] AC-04: Actions deep-link `?create=1&sourceType=investigation&sourceId=` locks parent and uses CAPA create API
- [x] AC-05: `GET /actions/?source_type=investigation` includes formal CAPAAction rows
- [x] AC-06: Explicit-title CAPA create is not idempotent (multiple CAPAs per investigation)
- [x] AC-07: FE + BE unit tests cover the above

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — Actions + InvestigationDetail + handoffLinks
- [x] Backend unit — CAPA investigation create + CAPA_ONLY filter recognition
- [ ] E2E — deferred to CI / staging

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Investigation → Create CAPA → submit → CAPA linked to investigation
- [x] **CUJ-02:** Investigation filter on Actions lists formal CAPAs
- [x] **CUJ-03:** Wrong parent Source ID 404 shows “Incident not found” (not “Action not found”)

## 7) Observability & Ops
- **Logs:** Existing console/error paths
- **Metrics:** Existing CAPA create metrics
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** From investigation with zero actions, Create CAPA → submit → see row on Actions tab + `/actions?sourceType=investigation&sourceId=…`
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Spot-check Investigation CAPA CTA + Actions list filter

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Broken CAPA create / missing investigation CAPAs in Actions list / misleading errors
- **Rollback steps:** Revert commit and redeploy
- **Owner:** David Harris / Platform ops

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
