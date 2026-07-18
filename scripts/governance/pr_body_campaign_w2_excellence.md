# Change Ledger (CL-CAMPAIGN-W2-EXCELLENCE)

## 1) Summary
- **Feature / Change name:** Wave 2 campaign excellence spine — compliance passport, evidence CSV, re-ack hook
- **User goal (1-2 lines):** Give engineers a compliance passport view of campaign assignments; let HSEC export assignment evidence as CSV; auto-spawn draft re-ack campaigns when a document version is published while active campaigns exist.
- **In scope:** O-07 passport API + page; O-09 evidence CSV API + client; O-10 `spawn_reack_campaign` service + publish hook + manual route; unit tests; Change Ledger
- **Out of scope:** O-08 Portal integration (follow-up); CampaignCompliance admin UI / JSON evidence export button (no component on main); full re-ack launch automation
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `MyCompliancePassport.tsx`; route `/my-compliance`; My Work nav link; `documentCampaignClient.ts` methods
- **Backend (handlers/services):** `document_campaign_service.py`; `document_campaign.py`; `documents.py`
- **APIs (endpoints changed/added):**
  - `GET /api/v1/document-campaigns/my-passport`
  - `GET /api/v1/document-campaigns/campaigns/{id}/evidence-pack.csv` (`document:update`)
  - `POST /api/v1/documents/{id}/spawn-reack-campaign` (`document:update`)
  - Best-effort `spawn_reack_campaign` on library document publish (`POST /documents/{id}/publish`)
- **Schemas/contracts:** `MyPassportResponse`, `SpawnReackCampaignResponse`
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — new endpoints only; publish hook is best-effort wrapped
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01 (O-07): `GET /document-campaigns/my-passport` returns outstanding, completed, stats from `CampaignAssignment` for current user
- [x] AC-02 (O-07): `/my-compliance` page + nav under My Work; Card/Badge list UI
- [x] AC-03 (O-09): CSV evidence export with user email, status, dates, quiz score/passed, signature_present, ip; `document:update` required
- [x] AC-04 (O-09): FE client method `downloadEvidencePackCsv` (no CampaignCompliance UI on main)
- [x] AC-05 (O-10): `spawn_reack_campaign` creates DRAFT follow-up from latest ACTIVE campaign audience/settings
- [x] AC-06 (O-10): Publish paths call hook in try/except; manual spawn route documented; publish never fails on hook error
- [x] AC-07: Unit tests for passport, CSV, spawn; frontend client tests

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `test_document_campaign_service.py`, `documentCampaignClient.test.ts`
- [x] Frontend — Layout nav test updated
- [ ] CI run — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Engineer opens Compliance Passport and sees stats + outstanding/completed lists
- [x] CUJ-02: HSEC downloads campaign evidence CSV via API/client
- [x] CUJ-03: Document publish with active campaign spawns draft re-ack (best-effort)

## 7) Observability & Ops
- **Logs:** Warning on re-ack hook failure after publish
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** Manual re-ack via `POST /documents/{id}/spawn-reack-campaign` if publish wiring insufficient

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Passport page load; CSV download; publish + verify draft campaign created
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health + smoke on `/my-compliance`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Passport/API errors or publish regressions
- **Rollback steps:** Revert PR; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation

## Follow-ups (deferred)
- **O-08 Portal:** Surface passport summary / outstanding count in portal My Work inbox
- **CampaignCompliance UI:** JSON + CSV export buttons when admin compliance panel lands on main
- **Re-ack automation:** Auto-launch draft re-ack campaigns or reset assignment statuses on publish

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
