# Change Ledger (CL-PORTAL-TOOLS-VAN)

## 1) Summary
- **Feature / Change name:** Employee Portal — My tool compliance + My van checks
- **User goal (1–2 lines):** Engineers see person-scoped tool expiry and van check/fault status on the portal home before Report / Work / Training.
- **In scope:** Self `/me` APIs; portal landing clear-to-work; `/portal/tools` and `/portal/van` detail pages; exclusive expiry bands matching Safety Asset Register
- **Out of scope:** Offline cache; weekly checklist type; fleet-wide defect lists; CES auto-create of engineers/vehicles
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `Portal.tsx` clear-to-work + tool/van tiles; `PortalMyTools.tsx`; `PortalMyVan.tsx`; `portalComplianceClient.ts`; App routes
- **Backend:** `portal_compliance_service.py`; `/portal/my-compliance|my-tools|my-van|drivers/me`; aliases `/assets/my-tools`, `/drivers/by-user/me`, `/vehicles/me/status`
- **APIs:** Additive person-scoped GET endpoints (HTTP 200 + empty_reason)
- **Schemas/contracts:** `src/api/schemas/portal_compliance.py`
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints; portal FE tolerates fetch failure (no silent zeros)
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert deploy

## 4) Acceptance Criteria (AC)
- [x] AC-01: Portal home shows My tool compliance and My van checks before Report
- [x] AC-02: Clear-to-work state is clear | attention | blocked from tool + van signals
- [x] AC-03: Tools = deduped union of owner_user_id + van kit with why_shown
- [x] AC-04: Van resolve via DriverProfile + registry verify; honest empty_reason
- [x] AC-05: Open defects scoped to my van only (not tenant-wide `/defects`)
- [x] AC-06: Cadence honesty — daily + monthly only (no fake weekly type)
- [x] AC-07: Fetch failure shows error, not fabricated zero badges
- [x] AC-08: Expiry bands use exclusive windows (overdue / due_30 / 60 / 90 / in_date) + quarantined

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_portal_compliance_service.py`
- [x] FE: `frontend/src/pages/__tests__/Portal.toolsVan.test.tsx`
- [ ] CI — after open / push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Portal home → tools / van detail routes
- [x] CUJ-02: Attention/blocked clear-to-work from overdue/quarantine/P1

## 7) Observability & Ops
- **Logs:** `portal_my_compliance` info line
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** Empty van → check DriverProfile.user_id + allocated_vehicle_reg / assigned_driver_id

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Login as linked driver with owned/van assets; confirm badges + detail lists
- **Canary plan:** N/A
- **Prod post-deploy checks:** Engineer portal home shows tool/van tiles; no call to tenant-wide defects from portal

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Portal home 5xx on my-compliance or wrong-tenant data exposure
- **Rollback steps:** Revert merge / redeploy prior SWA+API
- **Owner:** Platform / Fleet & Assets

## 10) Evidence Pack (links)
- CI run(s): after push
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
