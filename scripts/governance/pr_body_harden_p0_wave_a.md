# Change Ledger (CL-HARDEN-P0-A)

## 1) Summary
- **Feature / Change name:** Harden-P0 Wave A — Docs/Analytics 500s + Compliance honesty
- **User goal (1-2 lines):** Stop Library and Analytics blowing up with 500s; remove fake ISO Score numbers and RIDDOR “ready” stubs from Compliance Automation.
- **In scope:** documents list serialization hardening; executive-dashboard schema-safe fallbacks; Score tab live/empty only; RIDDOR prepare status `preparation_stub`; unit tests
- **Out of scope:** calendar tenant fail-closed, CAPA deep-link contract, evidenceAssetIds gate, complaint FK (Wave B)
- **Feature flag / kill switch:** N/A — fail-soft responses instead of 500

## 2) Impact Map (what changed)
- **Frontend:** `ComplianceAutomation.tsx` Score tab honest empty / live breakdown only
- **Backend:** `documents.py` list/get response coercion; `executive_dashboard` service + route validation fallbacks; `compliance_automation_service` RIDDOR prepare status
- **APIs:** `GET /documents/` and `GET /executive-dashboard` no longer 500 on legacy/partial data
- **Schemas/contracts:** Response validation tightened with empty fallbacks
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Tolerant reader — coerce bad JSON tags/keywords; empty KPI shells when subqueries fail
- **Breaking changes:** RIDDOR prepare status string changes `ready_to_submit` → `preparation_stub` (honesty)
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Documents list serializes legacy rows without 500
- [x] AC-02: Executive dashboard returns schema-valid payload when sub-aggregates fail
- [x] AC-03: Score tab has no hardcoded ISO 9001/14001/45001 demo scores
- [x] AC-04: RIDDOR prepare status is `preparation_stub`
- [x] AC-05: Unit tests for docs list, dashboard hardening, RIDDOR honesty

## 5) Testing Evidence
- [x] Unit — `pytest tests/unit/test_documents_list_response.py tests/unit/test_executive_dashboard_response_hardening.py tests/unit/test_riddor_prepare_honesty.py` (5 passed)
- [ ] CI — after open
- [ ] Staging/prod Playwright — Library + Analytics no 500; Score honest empty

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Library list loads without Internal server error
- [x] CUJ-02: Analytics/executive dashboard returns 200 with partial/empty shells
- [x] CUJ-03: Compliance Score shows honest empty (no 92% placeholders)

## 7) Observability & Ops
- **Logs:** Existing document/dashboard error logs retained
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan
- Staging verify Library + Analytics + Compliance Score
- Prod post-deploy: Playwright re-hit `/documents` and `/analytics`

## 9) Rollback Plan
- **Trigger:** New 500s or Score regression
- **Steps:** Revert PR squash commit; redeploy
- **Owner:** Platform

## 10) Evidence Pack
- CI: linked after open
- Source: 10-round Playwright assessment R6/R7 P0s

---

# Gate Checklist
- [x] Gate 0
- [x] Gate 1
- [ ] Gate 2 CI green
- [ ] Gate 3 staging
- [ ] Gate 4 N/A
- [x] Gate 5 prod plan
