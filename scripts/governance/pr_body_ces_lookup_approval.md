# Change Ledger (CL-CES-LOOKUP-APPROVAL)

## 1) Summary
- **Feature / Change name:** CES import — provisional Safety lookups + duplicate guards + Lookup Tables approval
- **User goal (1–2 lines):** Upload a full CES workbook so assets land in the register; new asset types/locations are created as pending approvals with strong near-duplicate prevention and confirmation.
- **In scope:** Similarity helper; CES dry-run proposals; commit confirmations + provisional types/locations; Admin Lookup Tables pending queue; notifications to superusers
- **Out of scope:** Auto-approving lookups; form LookupOption categories; auto-creating engineers/vehicles
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `SafetyAssetRegister.tsx` CES preview/confirm; `LookupTables.tsx` Safety pending queue; `safetyAssetsClient.ts`
- **Backend:** `ces_asset_import_service.py`, `lookup_similarity.py`, `safety_lookup_approval_service.py`, `asset_service.py` create guards, `assets.py` / `asset_imports.py` routes
- **APIs:** CES commit `confirmations` form field; `/assets/safety-lookups/*`
- **Schemas/contracts:** Additive CES report fields + Safety lookup schemas
- **Database:** `approval_status` + `source` on `asset_types` and `locations` (`20260804_safety_lu`)
- **Workflows/jobs/queues:** In-app/email notify superusers on provisional create
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive columns default `approved`; existing types/locations unchanged
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** Direct CES commit of similar names without confirmations now 422
- **Migration plan:** Alembic upgrade adds columns with server defaults
- **Rollback strategy (DB):** Downgrade drops columns; provisional rows remain as inactive if already created

## 4) Acceptance Criteria (AC)
- [x] AC-01: Dry-run no longer hard-fails all rows on UNKNOWN_TYPE; proposes new/similar lookups
- [x] AC-02: Similar names require explicit reuse-vs-create confirmation before commit
- [x] AC-03: Commit creates provisional (`pending`, inactive) types/locations and upserts assets
- [x] AC-04: Lookup Tables shows pending Safety queue with Approve / Use existing
- [x] AC-05: Manual Safety create blocks exact duplicates and warns on similar names

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_lookup_similarity.py`, CES import proposal/confirm tests
- [ ] CI — after open / push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Dry-run CES file → confirm similars → commit → assets created + pending lookups
- [x] CUJ-02: Admin Lookup Tables → Approve / merge pending Safety type

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** After CES commit, approve pending types/locations in Admin → Lookup Tables (`?pending=safety`)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Dry-run user CES workbook; confirm similars; commit; approve pending
- **Canary plan:** N/A
- **Prod post-deploy checks:** Commit no longer stuck on 1880 UNKNOWN_TYPE; pending queue visible

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Import creates duplicate types or approval queue broken
- **Rollback steps:** Revert merge / redeploy prior API+SWA
- **Owner:** Platform / Safety

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
