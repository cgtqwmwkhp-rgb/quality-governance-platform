# Change Ledger (CL-CAMPAIGN-CUJ-WAVE3)

## 1) Summary
- **Feature / Change name:** Campaign CUJ Wave 3 — O-11 reading queue unify (+ O-12 scaffold)
- **User goal (1-2 lines):** Portal My Work shows one honest reading queue: campaign assignments are SSOT; legacy policy-ack rows that duplicate active campaign work are hidden instead of opening `/documents/{policy_id}`.
- **In scope:** Shared `partitionReadingQueue` helper; PortalWork + MyReading dedupe; `linked_policy_id` on my-assignments; O-12 settings hook + TODO in `complete_assignment`; unit/FE tests; this Change Ledger
- **Out of scope:** O-14 Pinecone bulk; evidence PDF / re-ack auto-launch; global signed-url RBAC; full O-12 enforcement
- **Feature flag / kill switch:** `campaign_complete_competence_gate_enabled` default OFF (O-12 scaffold only)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `PortalWork.tsx`, `MyReading.tsx`, `campaignReadingHelpers.ts`, `documentCampaignClient.ts`
- **Backend (handlers/services):** `document_campaign.py` routes/schemas; `document_campaign_service.py` (O-12 TODO); `config.py`
- **APIs (endpoints changed/added):** `GET /document-campaigns/my-assignments` adds optional `linked_policy_id`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AssignmentResponse.linked_policy_id`
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** `CAMPAIGN_COMPLETE_COMPETENCE_GATE_ENABLED`, `CAMPAIGN_COMPLETE_COMPETENCE_GATE_FEATURE_FLAG`
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — new optional field; FE dedupe is client-side only
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert deploy only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Portal My Work pending reading count excludes suppressed duplicate policy-ack rows
- [x] AC-02: When policy-ack overlaps active campaign (linked_policy_id or legacy document_id), only campaign card renders
- [x] AC-03: Standalone policy-ack rows still render with legacy Open → `/documents/{policy_id}`
- [x] AC-04: My Reading admin list uses the same partition helper (campaign SSOT)
- [x] AC-05: `my-assignments` exposes `linked_policy_id` for honest overlap detection
- [x] AC-06: O-12 scaffold: settings + TODO at `complete_assignment` without blocking completion
- [x] AC-07: Unit/FE tests cover partition + PortalWork dedupe

## 5) Testing Evidence (link to runs)
- [x] FE unit — `campaignReadingHelpers.test.ts`, `PortalWork.test.tsx`
- [ ] Full CI — pending this PR
- [ ] Staging / prod smoke — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Portal → My Work → single campaign card when policy-ack duplicate exists
- [x] CUJ-02: Portal → My Work → standalone policy-ack still visible when no campaign overlap
- [x] CUJ-03: Admin My Reading → campaign + non-overlapping policy rows only

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Seed user with both policy-ack + campaign on same linked policy; confirm one card in portal My Work
- **Canary plan:** N/A
- **Prod post-deploy checks:** Pending reading badge count matches visible cards

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Missing policy-ack rows engineers still need; incorrect suppressions
- **Rollback steps:** Revert squash merge on main; redeploy previous tip
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
