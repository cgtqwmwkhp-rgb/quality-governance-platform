# Change Ledger (CL-CS-FRA-OCR-ELIGIBLE)

## 1) Summary
- **Feature / Change name:** Expose `fra_ocr_eligible` on Compliance Schedule requirements (pipeline slice 3)
- **User goal (1–2 lines):** Operators see FRA OCR ingest UI for every obligation the backend will accept — including catalogue `fire_risk_assessment` rows whose taxonomy is not `03.01` — instead of a FE taxonomy-only mismatch.
- **In scope:** `RequirementResponse.fra_ocr_eligible`; eager template load on requirement get/list/create/update/activate; FE helper reads server field; unit tests
- **Out of scope:** Slices 4–6 (from-evidence OCR, CAPA, Risk); Doc Graph; flag changes
- **Feature flag / kill switch:** None new — UI still gated by existing `compliance_schedule_fra_ocr` (default off). Eligibility field is informational and always computed.

## 2) Impact Map (what changed)
- **Frontend:** `complianceScheduleClient` type; `fraOcrHelpers.isFraOcrEligible`; FraOcr panel comment; related unit tests
- **Backend:** `RequirementResponse`; `_requirement_response`; `ComplianceScheduleFraOcrService.is_fra_ocr_eligible`; `selectinload(template)` / refresh on CS service paths
- **APIs:** Additive boolean on requirement responses
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** `test_compliance_schedule_fra_ocr_eligible_response.py`; eligibility helpers; FE helper tests

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive response field (default `false` in schema); older clients ignore it
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert deploy; FE falls back only if field absent (typed as required after this ship)

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| FRA OCR UI eligibility | FE taxonomy `03.01` only | Server matches `_is_fra_requirement` + active + site-scoped |
| Template-keyed FRA with edited taxonomy | Backend accepts; FE hid panel | `fra_ocr_eligible: true`; panel can show when flag on |
| Async lazy-load risk | N/A | Template eager-loaded / assigned before response map |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Template-keyed `fire_risk_assessment` requirement with taxonomy ≠ `03.01`, active, site-scoped → `fra_ocr_eligible: true`.
- [x] **AC-02:** Custom (no template) taxonomy `03.01`, active, site-scoped → `fra_ocr_eligible: true`.
- [x] **AC-03:** Inactive or org-wide (no `location_id`) → `fra_ocr_eligible: false`.
- [x] **AC-04:** FE `isFraOcrEligible` uses the server boolean (not taxonomy-only).
- [x] **AC-05:** Non-FRA template / taxonomy → `fra_ocr_eligible: false`.

## 5) Testing Evidence
- [x] Unit — `test_compliance_schedule_fra_ocr_eligible_response.py` + `test_is_fra_ocr_eligible_matches_load_gate` (6 passed locally)
- [x] FE — `fraOcrHelpers` + related compliance tests (36 passed locally via vitest)
- [x] Lint — black/isort/flake8 on touched Python
- [ ] Full CI — after PR open

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Operator opens site FRA activated from catalogue (taxonomy may differ from 03.01) → with FRA OCR flag on, Ingest panel appears because server sets `fra_ocr_eligible`.
- [x] **CUJ-02:** Operator opens org-wide or non-FRA obligation → panel stays hidden (`fra_ocr_eligible` false).

## 7) Observability & Ops
- **Logs:** No new log sites; eligibility is a response field only
- **Runbook:** N/A — no flag flip required for this slice

## 8) Release Plan
- Squash-merge to `main` → Main CI → Azure deploy → verify tip SHA on prod meta/version + health.
- No appsettings change; never full PUT of Azure appsettings.

## 9) Rollback Plan
- **Trigger:** Incorrect eligibility exposing OCR UI on non-FRA rows, or MissingGreenlet / 500s on requirement list/get
- **Rollback owner:** Platform / on-call (sole operator: David Harris)
- **Steps:**
  1. Revert squash commit on `main` and redeploy prior tip image
  2. If only FE wrong, hotfix FE helper; if BE wrong, revert takes precedence

## 10) Evidence Pack
- CI / staging / prod tip: linked after merge and LIVE verify

---

# Gate Checklist
- [x] Gate 0 — Scope lock + AC + Change Ledger (slice 3 only)
- [x] Gate 1 — Contracts (additive `fra_ocr_eligible`)
- [ ] Gate 2 — CI green
- [ ] Gate 3 — Staging verification
- [ ] Gate 4 — Canary (N/A — no write-path flag)
- [x] Gate 5 — Rollback via revert documented
