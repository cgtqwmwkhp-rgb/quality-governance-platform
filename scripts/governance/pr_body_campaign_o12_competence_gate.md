# Change Ledger (CL-CAMPAIGN-O12-COMPETENCE-GATE)

## 1) Summary
- **Feature / Change name:** O-12 — optional campaign assignment completion competence gate
- **User goal (1-2 lines):** When enabled per tenant, block campaign sign-off until the assignee's linked engineer profile clears the workforce competency gate for a configured asset type.
- **In scope:** Nullable `document_campaigns.competence_asset_type_id`; create/update schemas + PATCH draft route; enforcement in `complete_assignment` behind settings + feature flag; unit tests; `.env.example`; this Change Ledger
- **Out of scope:** FE launch panel wiring; `competency_gate_mode` changes for assessments/inductions; hard/soft mode for campaigns (always blocks when gate applies)
- **Feature flag / kill switch:** `campaign_complete_competence_gate_enabled` default OFF + tenant feature flag `campaign_complete_competence_gate`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `document_campaign_service.py` (`_enforce_complete_competence_gate_if_enabled`, create/update/spawn_reack); `document_campaign.py` routes; `document_campaign` model + schemas
- **APIs (endpoints changed/added):** `POST /document-campaigns/campaigns` accepts optional `competence_asset_type_id`; `PATCH /document-campaigns/campaigns/{id}` for draft updates; `CampaignResponse.competence_asset_type_id`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `CampaignCreateRequest`, `CampaignCreateRequestFE`, `CampaignUpdateRequest`, `CampaignResponse`
- **Database (migrations/entities/indexes):** Alembic `20260729_campaign_comp_gate` — nullable FK `document_campaigns.competence_asset_type_id` → `asset_types.id`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** `CAMPAIGN_COMPLETE_COMPETENCE_GATE_ENABLED`, `CAMPAIGN_COMPLETE_COMPETENCE_GATE_FEATURE_FLAG`
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — nullable column; default OFF enforcement
- **Breaking changes:** None (default no-op)
- **Migration plan:** Alembic upgrade adds nullable column + FK
- **Rollback strategy (DB):** Alembic downgrade drops column; revert deploy

## 4) Acceptance Criteria (AC)
- [x] AC-01: Enforcement only when `settings.campaign_complete_competence_gate_enabled` AND `FeatureFlagService.is_enabled`
- [x] AC-02: Nullable `competence_asset_type_id` on `document_campaigns` (model + migration)
- [x] AC-03: Create/update schemas expose optional field; draft PATCH route wired
- [x] AC-04: Soft-skip (log) when no linked Engineer or no `competence_asset_type_id`
- [x] AC-05: Gate not cleared → `BadRequestError` with actionable message
- [x] AC-06: Unit tests — flag off unchanged; flag on no asset allows; flag on fail blocks
- [x] AC-07: `.env.example` documents O-12 settings
- [x] AC-08: `competency_gate_mode` unchanged for assessments/inductions

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_document_campaign_service.py::TestCompleteAssignmentCompetenceGate`
- [ ] Full CI — pending this PR
- [ ] Staging / prod smoke — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Default deploy — completion unchanged (flag OFF)
- [x] CUJ-02: Flag ON + campaign without asset type — completion allowed (logged skip)
- [x] CUJ-03: Flag ON + asset type + uncleared gate — completion blocked with message

## 7) Observability & Ops
- **Logs:** INFO on soft-skip (no engineer link / no asset type configured)
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** Enable `CAMPAIGN_COMPLETE_COMPETENCE_GATE_ENABLED=true` and tenant feature flag; set `competence_asset_type_id` on campaigns requiring gate

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Enable flag on test tenant; create campaign with asset type; verify blocked/allowed paths
- **Canary plan:** N/A
- **Prod post-deploy checks:** Confirm default OFF — no behaviour change until explicitly enabled

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected completion blocks; incorrect gate skips
- **Rollback steps:** Set `CAMPAIGN_COMPLETE_COMPETENCE_GATE_ENABLED=false` or disable tenant feature flag; revert squash merge if needed
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): pending PR
- Staging deploy evidence: Linked after deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
