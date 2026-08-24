# Change Ledger (CL-CS-EVIDENCE-UPLOAD-SURFACES)

## 1) Summary
- **Feature / Change name:** Compliance Schedule evidence upload UX surfaces
- **User goal (1–2 lines):** Operators can attach proof when creating an obligation (optional past completion), when recording completion, and for each past occurrence — without hunting for a collapsed control.
- **In scope:** Create-form optional historical completion (files + completed_at → stage as `induction` → `completeRequirement` with `evidence_asset_ids`); discoverability copy/CTAs on detail, history rows, and completion sheet; i18n en+cy; FE unit tests.
- **Out of scope:** Obligation-level attachment table; FRA OCR / taxonomy 03.01 gating; Doc Graph; backend API changes.
- **Feature flag / kill switch:** Existing `COMPLIANCE_SCHEDULE_ENABLED` / FE `compliance_schedule` only. No new flag.

## 2) Impact Map (what changed)
- **Frontend:** `RequirementFormDialog.tsx` (historical evidence section on create); `RecordEvidenceSection.tsx` (visible upload CTA); `RecordCompletionSheet.tsx` (proof-of-completion copy); `ComplianceScheduleDetail.tsx` (helper text near Record completion + history); locales `en.json` / `cy.json`; unit tests.
- **Backend:** None
- **APIs:** None (reuses create + complete + evidence-assets upload)
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** RequirementFormDialog create→complete-with-evidence + partial-failure retry path; RecordEvidenceSection upload CTA

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE UX only; occurrence evidence remains on `compliance_record`.
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert FE commit / redeploy prior image.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Create obligation with past proof | Create only; no file path | Optional historical completion after create (same staging→rebind as Record completion) |
| Past occurrence upload discoverability | Collapsed muted toggle only | Visible “Upload documents for this past occurrence” CTA (panel still lazy) |
| Completion proof labelling | “Evidence (optional)” / “Add evidence files” | “Upload proof of completion” / “Upload proof files” |
| Failure honesty (create + evidence) | N/A | Obligation kept; clear error + link to detail to retry Record completion |
| Obligation-level attachments | None | Still none (locked) |
| FRA OCR | Separate panel | Untouched |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Create form offers optional “I have proof from a past completion” with multi-file + `datetime-local` completed_at (default now, past allowed); edit form does not.
- [x] **AC-02:** On create success with historical section on: stage uploads as `induction` / requirement id, then `completeRequirement` with `completed_at` + `evidence_asset_ids`.
- [x] **AC-03:** If complete/staging fails after create: staged assets discarded; dialog stays open with error that obligation was created; retry link to `/compliance-schedule/{id}`; no second create.
- [x] **AC-04:** Each history row shows a visible upload CTA without requiring the muted expand; list request still deferred until open.
- [x] **AC-05:** Record completion sheet labels make upload obvious (“Upload proof of completion”).
- [x] **AC-06:** Detail page helper text near Record completion CTA and occurrence list points operators at evidence per occurrence.

## 5) Testing Evidence
- [x] Unit — `RequirementFormDialog.test.tsx` (create→complete with evidence; partial failure retry); `RecordEvidenceSection.test.tsx` (CTA opens panel; still collapsed by default); `RecordCompletionSheet.test.tsx` still green
- [ ] Lint / typecheck / build — CI
- [ ] Integration / E2E — CI (module flag-gated in envs)

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Add obligation → enable past proof → attach file(s) → submit → occurrence recorded with evidence_asset_ids rebound.
- [x] **CUJ-02:** Open past occurrence row → Upload documents CTA → upload evidence onto that `compliance_record` (existing path, discoverability fixed).
- [x] **CUJ-03:** Record completion → Upload proof of completion → complete with staged evidence (existing path, copy strengthened).

## 7) Observability & Ops
- **Logs:** No new signals; uses existing create/complete/evidence-assets paths.
- **Runbook:** If create succeeds but complete fails, operator opens obligation detail and uses Record completion (or row upload after an occurrence exists).

## 8) Release Plan
- Squash-merge to `main` → Main CI → Azure deploy → verify ACA image tag = tip SHA and prod health.

## 9) Rollback Plan
- **Owner:** on-call maintainer / PR author at merge time
- **Rollback steps:** Revert squash commit on `main` and allow governed redeploy of prior image. No DB rollback. Feature is FE-only behind existing CS module flag.

## 10) Evidence Pack
- CI / staging / prod tip: linked after PR merges and deploy verifies LIVE

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** API/Data/UX contracts (occurrence evidence on compliance_record; create uses existing complete staging pattern)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
