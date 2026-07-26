# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Run021 Wave 2 — GROUP 6 error/validation honesty (remaining)
- **User goal (1–2 lines):** Failed saves and export actions must surface human-readable, persistent feedback — never raw Python enum reprs, silent buttons, or toast-only errors that vanish.
- **In scope:** Wire `humaniseCodedText` into `getApiErrorMessage` (PX-207 defence-in-depth); regression tests for Audit Pack (PX-252) and Risk Register Export (PX-293) already wired on main.
- **Out of scope:** PX-170 async states (#1321), PX-291 form primitive (#1315), PX-208 incident detail save banners (#1328 open), backend enum fix already in #1317, #1307 dependabot.
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/api/client.ts` — all server-composed API error strings pass through `humaniseCodedText`.
- **Backend (handlers/services):** None (complaint transition messages already use `.value` since #1317).
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.
- **Tests:** `client.test.ts` (PX-207), `ComplianceEvidence.test.tsx` (PX-252 tag), `RiskRegister.test.tsx` (PX-293 export).

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Frontend-only presentation of existing error payloads.
- **Tolerant reader / strict writer applied?** Yes — humanisation is no-op on plain English; status-code fallbacks unchanged.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Revert frontend deploy.

## 4) Acceptance Criteria (AC)
- [x] AC-01 (PX-207): Toast and persistent save banners never show `ComplaintStatus.FOO` — enum reprs humanised at API client layer.
- [x] AC-02 (PX-252): `/compliance` Audit Pack button issues `GET /api/v1/compliance/audit-pack` and downloads JSON (verified on main + regression test).
- [x] AC-03 (PX-293): `/risk-register` Export button downloads CSV of visible risks without faking success (verified on main + regression test).
- [x] AC-04 (PX-208 complaints): Complaint detail save failures leave persistent `FormNotice` after toast dismisses (already on main — not reworked).

## 5) Testing Evidence (link to runs)
- [x] Unit — vitest 64 passed locally (`client`, `displayLabels`, `ComplianceEvidence`, `RiskRegister`)
- [ ] Full CI — this PR
- [ ] Integration tests — N/A (frontend-only delta)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Complaint save rejected for invalid transition → error text reads "Acknowledged"/"Resolved", not Python repr.
- [x] CUJ-02: Compliance → Audit Pack → network call + file download.
- [x] CUJ-03: Risk register → Export → CSV download of loaded rows.

## 7) Observability & Ops
- **Logs:** None new.
- **Metrics:** None new.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Force a complaint status transition error; confirm toast/banner wording. Click Audit Pack and Risk Export.
- **Canary plan:** Standard train.
- **Prod post-deploy checks:** Same two export buttons + one forced save error spot-check.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Error messages garbled or export buttons regress.
- **Rollback steps:** Revert this PR / redeploy previous frontend bake.
- **Owner:** Platform / QGP maintainers

## 10) Evidence Pack (links)
- CI run(s): (filled by CI on this PR)
- Base branch: `main`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — frontend-only
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — n/a, full promote
- [x] **Gate 5:** Production verification plan + monitoring ready

## Defects addressed (Run021 GROUP 6 — remaining on main tip)

| ID | Status on main before this PR | This PR |
|---|---|---|
| **PX-207** | Backend fixed #1317; `humaniseCodedText` existed but was not wired to error surfacing | Wire into `getApiErrorMessage` + unit test |
| **PX-252** | Audit Pack already calls server endpoint | Regression test tagged PX-252 |
| **PX-293** | Export already downloads client-side CSV | Regression test tagged PX-293 |
| **PX-208 (complaints)** | Already has persistent `FormNotice` | Verified — skipped |
| **PX-208 (incidents)** | Open in #1328 | Skipped per scope |
| **PX-170** | #1321 AsyncState | Skipped |
| **PX-291** | #1315 form primitive | Skipped |
