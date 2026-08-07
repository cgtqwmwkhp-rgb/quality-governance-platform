# Change Ledger (CL-CS-FRA-OCR-CONFIRM-RISK)

## 1) Summary
- **Feature / Change name:** FRA OCR confirm → optional Risk proposal (pipeline slice 6)
- **User goal (1–2 lines):** On confirm, an operator may open one Enterprise Risk by entering likelihood and impact themselves — never from OCR ratings alone.
- **In scope:** Optional `risk` on confirm body; `COMPLIANCE_SCHEDULE_FRA_OCR_RISK_ENABLED` default OFF + deploy persistence; `RiskService.create_risk(commit=False)` for shared transaction; FE proposal block behind client feature flag; unit tests
- **Out of scope:** Auto risk from OCR `overall_risk_rating`; Doc Graph; changing ACTIONS/FRA OCR defaults; appsettings full PUT
- **Feature flag / kill switch:** `COMPLIANCE_SCHEDULE_FRA_OCR_RISK_ENABLED` / `compliance_schedule_fra_ocr_risk` — **default OFF**

## 2) Impact Map (what changed)
- **Frontend:** `FraOcrReviewSheet` optional risk block; client types; feature-flag default; en.json keys
- **Backend:** confirm schema + service; RiskService commit gate; feature catalogue
- **APIs:** Additive optional `risk` on confirm; additive `risks_created` on applied summary
- **Database:** None
- **Config/env/flags:** config + deploy-staging/production + env-vars.json
- **Dependencies:** `pypdf` 6.14.2 → 6.15.0 (CVE-2026-71852 Security Scan gate)
- **Tests:** flag-off/on confirm tests; `_create_risk_from_confirm` validation; empty-actions test unchanged

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive optional request field; default flag preserves no-risk behaviour
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback:** Set flag false / revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Risk from FRA OCR | Not created | Flag on + operator L×I only |
| OCR-invented scores | N/A | Forbidden — scores required on proposal |
| Empty confirm | No risk | Still no risk |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Flag OFF + risk payload → recorded on draft, `risks_created=0`, no RiskService create
- [x] **AC-02:** Flag ON + operator likelihood/impact → one Enterprise Risk (`source=fra_ocr_draft:{id}`), same confirm commit
- [x] **AC-03:** Flag ON + no risk payload → `risks_created=0` (no invent from OCR)
- [x] **AC-04:** Missing/out-of-range scores → ValidationError
- [x] **AC-05:** Empty-actions confirm test unchanged and green
- [x] **AC-06:** Deploy vars + env-vars persist flag (default false)

## 5) Testing Evidence
- [x] Unit — confirm risk gates + `test_fra_ocr_confirm_risk.py`
- [ ] Full CI — after PR open

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Flag off → Confirm with optional risk checked in UI (if shown) → no risk row
- [x] **CUJ-02:** Flag on → Enable propose risk, enter L=3 I=4 → confirm → RISK row in register
- [x] **CUJ-03:** Flag on → Confirm without proposing risk → due date only / CAPAs per other flags

## 7) Observability & Ops
- **Logs:** confirm includes `risks_created`; audit payload `risk_reference`
- **Runbook:** `gh variable set COMPLIANCE_SCHEDULE_FRA_OCR_RISK_ENABLED --body true|false`; merge-only appsettings (never full PUT)

## 8) Release Plan
- Squash-merge → Main CI → staging → prod → verify tip SHA + health. Leave flag false until bake.

## 9) Rollback Plan
- Trigger: unexpected risk volume / wrong scores
- Steps: set var false; merge-only appsettings false; revert squash if needed

## 10) Evidence Pack
- Linked after LIVE verify

---

# Gate Checklist
- [x] Gate 0 — Scope lock (slice 6 only)
- [x] Gate 1 — Contracts (optional risk; flag default off)
- [ ] Gate 2 — CI green
- [ ] Gate 3 — Staging
- [ ] Gate 4 — Canary N/A (flag off)
- [x] Gate 5 — Rollback documented
