# Change Ledger (CL-GOV-LIB-W4A-APPROVE-CAMPAIGN)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W4a — HSEQ approve → optional DocumentCampaign offer
- **User goal (1–2 lines):** After HSEQ approves a filed all-staff library document, the API returns an optional campaign offer; confirming creates a draft DocumentCampaign (launch opt-in) reusing the existing campaign stack.
- **Depends on:** #1180 LIVE (W3 on tip `af9ee60`); W1 lifecycle approve; DocumentCampaign create/launch
- **In scope:** `campaign_offer` on approve response; `POST /documents/{id}/offer-campaign`; eligibility (filed + approved + all_staff); FE lifecycle CTAs + post-approve HSEQ offer; unit tests; Change Ledger
- **Out of scope:** Auto-launch on approve; statutory/overdue/open-pack dashboard tiles (W4b); pel_doc_ref dependency map (W4b); disposal (W5); second reading stack
- **Feature flag / kill switch:** None — opt-in offer; default `launch=false`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `DocumentDetail.tsx` — submit/approve/reject CTAs + HSEQ offer banner; `DocumentCampaignPanel.tsx` — HSEQ title copy
- **Backend (handlers/services):** `document_library_campaign_offer_service.py`
- **APIs (endpoints changed/added):** `POST /documents/{id}/approve` (+ optional `campaign_offer`); `POST /documents/{id}/offer-campaign`
- **Schemas/contracts:** Additive OpenAPI only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive response field + new POST; tolerant FE readers
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert commit only
- Approve remains atomic; campaign create is a separate confirm POST

## 4) Acceptance Criteria (AC)
- [x] AC-01: Approve response includes `campaign_offer.eligible=true` for filed approved `all_staff` docs
- [x] AC-02: Offer ineligible for missing category / non-approved / managers|restricted access (reason codes)
- [x] AC-03: `POST .../offer-campaign` creates draft via `DocumentCampaignService.create_campaign` (`all_users`)
- [x] AC-04: `launch=false` default; `launch=true` calls existing launch path
- [x] AC-05: Existing draft → `offered=false`, `reason=draft_already_exists`
- [x] AC-06: ACL deny when actor cannot read the library document
- [x] AC-07: FE shows Submit / Approve / Reject; post-approve HSEQ offer; panel labelled HSEQ
- [x] AC-08: Unit tests + Change Ledger (Gates 0–5)

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_gov_lib_w4_approve_campaign.py` (local)
- [ ] CI — this PR
- [ ] Staging verification — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: HSEQ approves filed all-staff doc → offer eligible → confirm draft campaign
- [x] CUJ-02: Managers-access doc → offer ineligible (`access_level_managers`)
- [x] CUJ-03: Second offer with existing draft → idempotent draft id
- [x] CUJ-04: Self-approve still blocked by W1 lifecycle (unchanged)

## 7) Observability & Ops
- **Logs:** Existing campaign create/launch logs; no new metrics
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** HSEQ uses Document detail Approve → optional “Launch HSEQ reading campaign”

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Approve filed all-staff doc; confirm offer; open draft in campaign panel; decline path leaves no campaign
- **Canary plan:** N/A — additive/opt-in
- **Prod post-deploy checks:** tip_match YES; approve response includes `campaign_offer`; My Reading unchanged until launch

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Spurious campaign drafts or approve response schema break FE
- **Rollback steps:** Revert PR on main; force_deploy prior SHA
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After tip deploy
- Canary evidence (if applicable): N/A
- Unit evidence: `pytest tests/unit/test_gov_lib_w4_approve_campaign.py`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (additive-only)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A, additive/opt-in rollout
- [x] **Gate 5:** Production verification plan + monitoring ready
