# Change Ledger (CL-CAMPAIGN-W1-SNOOZE-GROUP)

## 1) Summary
- **Feature / Change name:** Wave 1 — O-04 reminder snooze + O-06 compliance by group
- **User goal (1-2 lines):** Let engineers defer campaign reminders for up to 7 days from My Reading, and give HSEC admins per-engineer-group compliance breakdown on the campaign compliance dashboard.
- **In scope:** `snooze_until` column + migration; snooze API; reminder sweep snooze skip; compliance list + by-group APIs; My Reading snooze button; admin CampaignCompliance page with expandable group rows; unit tests; Change Ledger
- **Out of scope:** Reminder defaults UI (#1149), evidence export, question inbox, merge of #1149 branch
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `MyReading.tsx` snooze button; new `admin/CampaignCompliance.tsx`; route `/admin/campaign-compliance`
- **Backend (handlers/services):** `document_campaign_service.py` — snooze, `process_due_reminders`, `list_compliance_summary`, `compliance_by_group`; Celery task `document_campaign_tasks.py`
- **APIs (endpoints changed/added):** `POST /document-campaigns/assignments/{id}/snooze`; `GET /document-campaigns/compliance`; `GET /document-campaigns/compliance/{campaign_id}/by-group`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Snooze + compliance/group response schemas; FE client types
- **Database (migrations/entities/indexes):** `campaign_assignments.snooze_until` (nullable DateTime, indexed)
- **Workflows/jobs/queues (if any):** `process_campaign_reminders` Celery task
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — nullable column; new endpoints only
- **Breaking changes:** None
- **Migration plan:** Alembic `20260727_campaign_snooze` chained from `20260718_doc_campaign`
- **Rollback strategy (DB):** Downgrade migration drops column/index

## 4) Acceptance Criteria (AC)
- [x] AC-01 (O-04): `snooze_until` on CampaignAssignment with migration from tip head
- [x] AC-02 (O-04): `POST /assignments/{id}/snooze` body `{ hours: 1-168 }`, CurrentUser own assignment only
- [x] AC-03 (O-04): `process_due_reminders` skips reminder send when `snooze_until > now`, still marks overdue
- [x] AC-04 (O-04): My Reading shows "Snooze 24h" on pending/overdue campaign items
- [x] AC-05 (O-06): `GET /compliance/{campaign_id}/by-group` returns per-group + Ungrouped metrics
- [x] AC-06 (O-06): CampaignCompliance admin page expands group breakdown when audience groups present
- [x] AC-07: Unit tests for snooze, reminder skip, and group compliance

## 5) Testing Evidence (link to runs)
- [ ] Lint — pending CI
- [ ] Typecheck — pending CI
- [ ] Unit tests — pending CI
- [ ] Integration tests — deferred to CI (requires DB)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Engineer snoozes pending campaign assignment from My Reading
- [x] CUJ-02: Reminder job marks overdue but defers notification while snoozed
- [x] CUJ-03: HSEC admin views campaign compliance and expands group breakdown

## 7) Observability & Ops
- **Logs:** Celery task logs reminder sweep counts
- **Metrics:** No change
- **Alerts:** No change

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Run migration; smoke snooze + compliance endpoints
- **Canary plan:** N/A
- **Prod post-deploy checks:** Migration applied; My Reading snooze visible

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Snooze or compliance API failures
- **Rollback steps:** Revert PR; downgrade migration if deployed
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
