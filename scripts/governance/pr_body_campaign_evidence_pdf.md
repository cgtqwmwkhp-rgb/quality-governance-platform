# Change Ledger (CL-CAMPAIGN-DEF-PDF)

**Path claim:** `after-def-pdf`

## 1) Summary
- **Feature / Change name:** DEF-PDF — Campaign evidence pack PDF export
- **User goal (1-2 lines):** Let HSEC export campaign assignment evidence as a shareable PDF (same rows as CSV) from admin compliance and document results screens.
- **In scope:** `fpdf2` dependency; `build_evidence_pack_pdf` service; `GET .../evidence-pack.pdf`; FE blob download helpers + CSV/PDF buttons; unit tests; Change Ledger
- **Out of scope:** Re-ack auto-launch; UVDB; Planet Mark; JSON evidence pack changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `CampaignCompliance.tsx`; `DocumentCampaignResults.tsx`; `documentCampaignClient.ts`
- **Backend (handlers/services):** `document_campaign_service.py`; `document_campaign.py`
- **APIs (endpoints changed/added):**
  - `GET /api/v1/document-campaigns/campaigns/{id}/evidence-pack.pdf` (`document:update`)
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** `fpdf2` added to `requirements.txt` (pypdf remains read-only)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — new endpoint + UI buttons only
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: `build_evidence_pack_pdf` returns PDF bytes with campaign header + same assignment columns as CSV
- [x] AC-02: `GET .../evidence-pack.pdf` streams `application/pdf` with `document:update` auth (mirrors CSV)
- [x] AC-03: FE `downloadEvidencePackPdf` triggers browser download; `downloadEvidencePackCsv` fixed to trigger blob download
- [x] AC-04: CSV + PDF export buttons on CampaignCompliance and DocumentCampaignResults
- [x] AC-05: Unit tests beside `TestBuildEvidencePackCsv`; frontend client tests for CSV/PDF blob download

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `test_document_campaign_service.py`, `documentCampaignClient.test.ts`
- [ ] CI run — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: HSEC opens Campaign Compliance → Export PDF → file downloads
- [x] CUJ-02: HSEC opens Document results → Export CSV/PDF → files download

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** None

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** CSV + PDF download from compliance table and document results tab
- **Canary plan:** N/A
- **Prod post-deploy checks:** Smoke download on one campaign

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** PDF generation errors or download regressions
- **Rollback steps:** Revert PR; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Builds on: O-09 CSV evidence export (Wave 2 excellence)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
