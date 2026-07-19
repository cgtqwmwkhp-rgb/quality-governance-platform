# Change Ledger (CL-CAMPAIGN-DEF-AUTO)

## 1) Summary
- **Feature / Change name:** DEF-AUTO — re-ack campaign auto-launch after spawn
- **User goal (1-2 lines):** When a document version is published and a re-ack campaign is spawned, optionally auto-launch the follow-up campaign and close the superseded active campaign so engineers are not served dual ACTIVE assignments.
- **In scope:** Settings + feature flag (default OFF); `spawn_reack_campaign` auto-launch + source close; publish hook unchanged (best-effort); manual `?auto_launch=true` opt-in; response schema extension; unit tests; this Change Ledger
- **Out of scope:** Evidence PDF; UVDB/PM; assignment status reset; frontend UI
- **Feature flag / kill switch:** `campaign_reack_auto_launch_enabled` default OFF + `campaign_reack_auto_launch` feature flag

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `document_campaign_service.py`; `documents.py` spawn route; `config.py`
- **APIs (endpoints changed/added):**
  - `POST /api/v1/documents/{id}/spawn-reack-campaign?auto_launch=true` (optional query param)
  - Publish hook (`POST /documents/{id}/publish`) — same best-effort spawn; auto-launch when settings + flag enabled
- **Schemas/contracts:** `SpawnReackCampaignResponse` adds `launched`, `launch_error`
- **Database:** None (uses existing `closed_at` / `CampaignStatus.CLOSED`)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** `CAMPAIGN_REACK_AUTO_LAUNCH_ENABLED`, `CAMPAIGN_REACK_AUTO_LAUNCH_FEATURE_FLAG`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive; default OFF preserves O-10 draft-only behaviour
- **Tolerant reader / strict writer applied?** Yes — new response fields optional; launch failure leaves draft
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: `campaign_reack_auto_launch_enabled` defaults OFF in settings + `.env.example`
- [x] AC-02: Feature flag key `campaign_reack_auto_launch` documented (O-12 pattern)
- [x] AC-03: After successful spawn, when settings AND feature flag enabled → `launch_campaign` runs
- [x] AC-04: On successful auto-launch, source campaign set to CLOSED with `closed_at`
- [x] AC-05: Publish hook remains best-effort; launch failure logs warning and leaves draft
- [x] AC-06: `SpawnReackCampaignResponse` includes `launched` and `launch_error`
- [x] AC-07: Manual route supports `?auto_launch=true` opt-in
- [x] AC-08: Unit tests — flag off draft only; flag on launches + closes source

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `test_document_campaign_service.py` (`TestSpawnReackCampaign`)
- [ ] CI run — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Publish with flag OFF — draft re-ack only (unchanged O-10)
- [x] CUJ-02: Publish with flag ON — re-ack launched, source closed, no dual ACTIVE
- [x] CUJ-03: Manual spawn with `auto_launch=true` launches without env flag

## 7) Observability & Ops
- **Logs:** Warning on re-ack auto-launch failure (draft retained)
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** Enable `CAMPAIGN_REACK_AUTO_LAUNCH_ENABLED=true` + feature flag per tenant when ready

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Publish doc with active campaign; verify draft-only (flag off); enable flag and verify launch + source close
- **Canary plan:** Enable flag for pilot tenant only
- **Prod post-deploy checks:** Publish smoke; confirm no dual ACTIVE campaigns

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Dual ACTIVE campaigns or launch failures blocking publish
- **Rollback steps:** Disable feature flag; set `CAMPAIGN_REACK_AUTO_LAUNCH_ENABLED=false`; revert PR if needed
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
