# Change Ledger (CL-CAMPAIGN-RESULTS-W1)

## File allowlist (exclusive)
- `src/api/routes/document_campaign.py`
- `src/api/schemas/document_campaign.py`
- `src/domain/services/document_campaign_service.py`
- `tests/unit/test_document_campaign_service.py`
- `frontend/src/api/documentCampaignClient.ts`
- `frontend/src/api/documentCampaignClient.test.ts`
- `frontend/src/api/client.ts` (re-export roster types only)
- `frontend/.size-limit.json` (index budget 161→162 kB for roster i18n)
- `frontend/src/pages/CampaignRosterPanel.tsx` (NEW)
- `frontend/src/pages/DocumentCampaignResults.tsx` (NEW)
- `frontend/src/pages/DocumentCampaignPanel.tsx`
- `frontend/src/pages/DocumentDetail.tsx`
- `frontend/src/pages/documentEvidenceTab.ts`
- `frontend/src/pages/admin/CampaignCompliance.tsx`
- `frontend/src/pages/__tests__/documentEvidenceTab.test.ts`
- `frontend/src/pages/__tests__/CampaignRosterPanel.test.tsx` (NEW)
- `frontend/src/i18n/locales/en.json`
- `scripts/governance/pr_body_campaign_results_wave1.md`

**Zero overlap** with Layout.tsx, App.tsx, Alembic, Audits.tsx, IMSDashboard.tsx.

## 1) Summary
- **Feature / Change name:** Campaign Results Wave 1 — document-local + central who-read roster
- **User goal:** HSEQ admins can see live completion, open rate, overdue, quiz pass/fail, and a filterable assignee roster on the document and in Admin Campaign Compliance — without downloading CSV.
- **In scope:** Roster API; Document **Campaign results** tab; shared roster panel; central expand roster + deep links; launch-panel KPI chips; vitest/unit tests; Change Ledger
- **Out of scope:** Wave 2 analytics trends/score histograms/library badges; reminder send from roster; policy-ack unify
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map
- **Frontend:** DocumentDetail tab `campaign-results`; CampaignCompliance expandable roster
- **Backend:** `GET /api/v1/document-campaigns/campaigns/{id}/roster`
- **APIs / schemas:** CampaignRoster* models
- **Database / jobs:** None

## 3) Compatibility & Data Safety
- Additive API + UI; evidence pack unchanged
- Breaking changes: None
- Rollback: Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: HSEC with `document:update` can list paginated roster with status/q/opened/quiz_passed filters
- [x] AC-02: Document detail has **Campaign results** tab with KPIs + live roster
- [x] AC-03: Admin Campaign Compliance expands any campaign to the same roster + links to document results
- [x] AC-04: Launch panel shows completion/overdue chips + View results deep link when launched
- [x] AC-05: Empty states are honest (no demo assignees)
- [x] AC-06: Unit + vitest coverage for roster service, client path, tab whitelist, roster panel

## 5) Testing Evidence
- [x] `python3.11 -m pytest tests/unit/test_document_campaign_service.py::TestListCampaignRoster -q` — 2 passed
- [x] `cd frontend && npx vitest run src/api/documentCampaignClient.test.ts src/pages/__tests__/documentEvidenceTab.test.ts src/pages/__tests__/CampaignRosterPanel.test.tsx` — 15 passed
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Document → Campaign results → see who opened / scored
- [x] **CUJ-02:** Admin Campaign Compliance → expand → roster + Document results link
- [x] **CUJ-03:** Share/Quiz panel → View results deep link

## 7) Observability & Ops
- No change

## 8) Release Plan
- Spot-check prod after deploy: `/documents/{id}?tab=campaign-results`, `/admin/campaign-compliance`

## 9) Rollback Plan
- Trigger: Roster 500s or blank document tab
- Steps: Revert commit, redeploy

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Allowlist exclusive
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary N/A
- [x] **Gate 5:** Prod verification plan ready
