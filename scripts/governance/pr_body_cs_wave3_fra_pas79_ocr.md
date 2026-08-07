# Change Ledger (CL-CS-W3-PR-FRA-PAS79-OCR)

## 1) Summary
- **Feature / Change name:** Wave 3 — FRA / PAS79 OCR ingest (propose → confirm)
- **User goal (1–2 lines):** On a site-scoped Fire Risk Assessment obligation, an operator can upload a PAS79-style FRA PDF, review extracted fields and Priority Action Plan rows with provenance, and only then update `next_due_date` (and optionally file the PDF into Governance Library under taxonomy 03.01).
- **In scope:** `fra_pas79` DocumentIntelligence purpose; parser + draft table; upload / list / get / confirm / discard / file routes; feature flag `compliance_schedule_fra_ocr` (default off); obligation-detail Ingest panel; unit + API tests; DPIA logging honesty
- **Out of scope:** CAPA auto-create from Priority Actions (drafts recorded only — CAPASource label lands in a follow-up); pre-egress OCR redaction (E4 accepted residual); portal ingest; bulk multi-FRA zip; dual-OCR dispute UX; PersonNameField for assessor; org-wide FRA ingest
- **Feature flag / kill switch:** `COMPLIANCE_SCHEDULE_ENABLED` + kill switch (routes 404 when closed) **and** `COMPLIANCE_SCHEDULE_FRA_OCR_ENABLED` / client `compliance_schedule_fra_ocr` (default false). Filing confirm path requires `document:create` in addition to `compliance_schedule:update`.

## 2) Impact Map (what changed)
- **Frontend:** `ComplianceScheduleDetail` + `FraOcrPanel` / upload / review sheet / filing control; `useFeatureFlag` default; API client
- **Backend:** `fra_pas79_ocr_service`, `compliance_schedule_fra_ocr_service`, CS routes under nested FRA OCR router, schemas, model, migration + RLS adopt
- **APIs:** See §4 routes (additive)
- **Database:** `compliance_schedule_ocr_drafts` + RLS
- **Config/env/flags:** `compliance_schedule_fra_ocr_enabled`
- **Dependencies:** None new
- **Tests:** Parser fixtures, apply/confirm human-gate, no-OCR-text-in-logs AST gate, FE review-sheet gate

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive; flag default off; no change to complete/file occurrence paths
- **Breaking changes:** None
- **Migration plan:** Forward-only create table + RLS; discard orphan blobs best-effort (no sweeper in this PR — named follow-on)
- **Rollback strategy (DB):** Revert code; table can remain empty (flag off). Do not drop enum labels in a hurry.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| FRA PDF → schedule | Manual due-date edit; evidence only on occurrences | Propose→confirm ingest on site FRA detail; human must submit `next_due_date` |
| Automated decisions | N/A | No auto-apply; confirm is the gate |
| OCR logging | Shared spine | No document body / full OCR / evidence snippets in structured logs (AST-tested) |
| Library filing | Occurrence `/file` only | Separate `/fra-ocr/drafts/{id}/file` after confirm; category must be taxonomy 03.01 |
| Pre-egress redaction | E4 follow-on open | Still deferred (accepted residual #1619) — not claimed shipped |
| CAPA from Priority Actions | N/A | Actions stored on draft only (`actions_created=0`) |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Upload PDF on site-scoped `fire_risk_assessment` / taxonomy `03.01` creates a `pending` draft with proposed fields + Priority Action rows (or empty proposal + warning when OCR yields no text — fail soft)
- [x] AC-02: Confirm requires explicit `next_due_date` in the request body; refuses non-pending drafts; writes only `requirement.next_due_date` (never `last_completed_at`); records confirmed actions without creating CAPAs
- [x] AC-03: Discard marks draft discarded; org-wide / inactive / non-FRA requirements rejected
- [x] AC-04: File-to-library only after confirm; requires `document:create`; category taxonomy must be `03.01`
- [x] AC-05: Module closed or FRA OCR flag off → 404; UI panel hidden when flag off / ineligible
- [x] AC-06: Logs must not include OCR text / evidence snippets (unit AST gate)

## 5) Testing Evidence
- [ ] Lint / typecheck / build — CI
- [x] Unit — parser fixtures + confirm/discard + no-text-in-logs
- [ ] Integration — CI
- [x] FE — review sheet human-gate + panel visibility

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Operator opens site FRA → Ingest FRA report → upload sample PAS79 PDF → review → confirm new due date → requirement updates
- [x] CUJ-02: After confirm → File to Library under 03.01 → draft `filing_status=filed`

## 7) Observability & Ops
- **Logs:** draft_id, requirement_id, tenant_id, extraction_method, ocr_provider_status, counts, exception type — never OCR body
- **Runbook:** Enable `COMPLIANCE_SCHEDULE_FRA_OCR_ENABLED` only after CS module is on and QGP DI / Mistral readiness understood

## 8) Release Plan
- Staging: flag on for bake; run CUJ-01/02 with a redacted FRA PDF
- Prod: tip `build_sha` match; flag remains off until bake sign-off unless explicitly enabled

## 9) Rollback Plan
- **Trigger:** Wrong due dates applied without review, OCR text in logs, filing under wrong taxonomy, CAPAs created unexpectedly
- **Steps:** Set `COMPLIANCE_SCHEDULE_FRA_OCR_ENABLED=false`; revert squash if needed; redeploy prior image

## 10) Evidence Pack
- CI / staging / prod tip: linked after PR

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** API/Data/UX contracts (propose→confirm; filing separate; actions draft-only)
