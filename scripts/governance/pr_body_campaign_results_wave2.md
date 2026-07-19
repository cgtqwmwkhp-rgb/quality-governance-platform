# Change Ledger (CL-CAMPAIGN-RESULTS-W2)

## File allowlist (exclusive)
- `src/api/schemas/document_campaign.py`
- `src/api/routes/document_campaign.py`
- `src/domain/services/document_campaign_service.py`
- `tests/unit/test_document_campaign_service.py`
- `frontend/src/api/documentCampaignClient.ts`
- `frontend/src/api/documentCampaignClient.test.ts`
- `frontend/src/api/client.ts` (re-export wave 2 types)
- `frontend/src/pages/CampaignCommandKpis.tsx` (NEW)
- `frontend/src/pages/CampaignAnalyticsPanel.tsx` (NEW)
- `frontend/src/pages/CampaignPeopleChase.tsx` (NEW)
- `frontend/src/pages/admin/CampaignCompliance.tsx`
- `frontend/src/pages/Documents.tsx`
- `frontend/src/pages/documentCampaignHelpers.ts`
- `frontend/src/pages/__tests__/CampaignCommandKpis.test.tsx` (NEW)
- `frontend/src/pages/__tests__/CampaignAnalyticsPanel.test.tsx` (NEW)
- `frontend/src/pages/__tests__/CampaignPeopleChase.test.tsx` (NEW)
- `frontend/src/pages/__tests__/Documents.test.tsx`
- `frontend/.size-limit.json` (162→163 kB for Command UI)
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_campaign_results_wave2.md`

## 1) Summary
- **Feature / Change name:** Campaign Results Wave 2 — Campaign Command analytics + library badges
- **User goal:** HSEQ admins see portfolio KPIs, 14-day trend, per-campaign funnel/score analytics, cross-campaign chase lists, and document-library campaign health badges without exports.
- **In scope:** Overview / analytics / people APIs; Command KPI strip; analytics panel on expand; chase section; library badges; vitest; Change Ledger
- **Out of scope:** Reminder send from chase; new chart libraries; policy-ack unify
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map
- **Frontend:** Admin Campaign Compliance upgraded to Campaign Command; Documents library badges
- **Backend:** `GET /compliance/overview`, `GET /campaigns/{id}/analytics`, `GET /compliance/people`
- **APIs / schemas:** ComplianceOverview*, CampaignAnalytics*, CompliancePeople*
- **Database / jobs:** None

## 3) Compatibility & Data Safety
- Additive API + UI; Wave 1 roster unchanged
- Breaking changes: None
- Rollback: Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Portfolio overview shows active campaigns, completion %, overdue, quiz fails, open rate + 14-day series
- [x] AC-02: Expanded campaign shows analytics funnel + score histogram above roster
- [x] AC-03: Chase section tabs overdue vs quiz_fail with deep links to document results
- [x] AC-04: Documents list shows campaign health badge when compliance row exists
- [x] AC-05: Loading/error/empty states are honest (no placeholder progress)
- [x] AC-06: Client + component vitest coverage for new endpoints and panels

## 5) Testing Evidence
- [ ] `python3.11 -m pytest tests/unit/test_document_campaign_service.py -k "Overview or Analytics or People" -q`
- [ ] `cd frontend && npx vitest run src/api/documentCampaignClient.test.ts src/pages/__tests__/CampaignCommandKpis.test.tsx src/pages/__tests__/CampaignAnalyticsPanel.test.tsx src/pages/__tests__/CampaignPeopleChase.test.tsx`
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [ ] **CUJ-01:** Admin Campaign Compliance → portfolio KPIs + trend
- [ ] **CUJ-02:** Expand campaign → analytics + roster
- [ ] **CUJ-03:** Chase tab → open document results
- [ ] **CUJ-04:** Documents library → campaign badge → results tab

## 7) Observability & Ops
- No change

## 8) Release Plan
- Spot-check: `/admin/campaign-compliance`, `/documents` with active campaigns

## 9) Rollback Plan
- Trigger: Overview/analytics 500s or misleading badges
- Steps: Revert commit, redeploy

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Allowlist exclusive
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
