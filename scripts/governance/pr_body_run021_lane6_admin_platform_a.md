# Change Ledger (CL-RUN021-LANE6-ADMIN-PLATFORM-A)

## 1) Summary
- **Feature / Change name:** Run021 Wave-next Lane 6 slice A — Admin + Platform residual honesty
- **User goal:** Admin/platform screens stop misrouting, stop presenting blank/black settings as live branding, allow rejecting junk lookup imports, and describe Form Builder emptiness honestly.
- **In scope:** Contracts route wiring; System Settings load/save + branding/contact/regional honesty; pending lookup Reject/discard; HSEQ inbox route spelling; Form Builder / Active Forms honesty; staff `/help`; notification ISO date rewrite; tests; Change Ledger
- **Out of scope:** Portal*, Investigations*, Actions*, Case registers*, Incidents/Complaints/NearMiss/RTA*, Analytics/Dashboard/Compliance*, Audits/UVDB/Assurance*, bulk `en.json`/`cy.json` localisation, `employeePickerUtils.ts`, production data cleanup (test users/groups/hours)
- **Defects addressed:** PX-274, PX-227, PX-228, PX-229, PX-196, PX-269, PX-186, PX-272, PX-161, PX-187

## 2) Impact Map
- **Backend:** `safety_lookup_approval_service.reject` discard-when-unused; `SafetyLookupRejectRequest`; assets reject route
- **Frontend:** `App.tsx` routes; `SystemSettings` + helpers; `AdminDashboard`; `FormsList`; `LookupTables`; `Layout` HSEQ path; `Notifications` date honesty; `StaffHelp`
- **APIs:** Reject pending safety lookup without required `target_id` when unused
- **Database:** None

## 3) Compatibility & Data Safety
- **Strategy:** Additive honesty + correct routing; reject discard refused when assets still reference the provisional lookup
- **Breaking changes:** None — unused provisional lookups can now be discarded; `/admin/hsec-inbox` redirects to `/admin/hseq-inbox`
- **Rollback:** Revert PR

## 4) Acceptance Criteria
- [x] AC-01: `/admin/contracts` renders Contracts Management (not Lookup Tables)
- [x] AC-02: System Settings loads API values; branding does not default to empty/#000000 as if live
- [x] AC-03: Empty support contact shows honesty banner
- [x] AC-04: Regional date_format/timezone/language are constrained selects
- [x] AC-05: Pending Safety lookups expose Reject; unused rows can be discarded
- [x] AC-06: Admin HSEQ Inbox path is `/admin/hseq-inbox` with legacy redirect
- [x] AC-07: Active Forms 0 / empty Form Builder copy does not claim “no forms in service”
- [x] AC-08: `/help` renders staff help (not 404)
- [x] AC-09: Notification body ISO dates rewrite to DD/MM/YYYY
- [x] AC-10: Unit/component tests cover the above

## 5) Testing Evidence
- [x] `npx vitest run` (targeted admin/settings/lookups/layout/notifications helpers) — 60 passed
- [x] `python3.11 -m pytest tests/unit/test_safety_lookup_reject.py` — 2 passed

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Admin → System Settings → load shows API values; empty branding/contact surfaces honesty (not live defaults)
- [x] **CUJ-02:** Admin → Lookup Tables → pending Safety row → Reject unused provisional → discarded; in-use row refused without merge
- [x] **CUJ-03:** Admin Dashboard → Form Builder count 0 → copy does not claim “no live forms in service”
- [x] **CUJ-04:** Navigate `/admin/contracts` and `/admin/hseq-inbox` (legacy `/admin/hsec-inbox` redirects) → correct screens

## 7) Observability & Ops
- **Logs / metrics / alerts:** No new metrics; reject-with-usage raises ValidationError (existing API error path); admin load soft-fail uses existing capture helpers

## 8) Release Plan
- **Staging:** Spot-check contracts route, System Settings honesty, lookup Reject, Form Builder zero copy, `/help`, HSEQ inbox path
- **Prod post-deploy:** Same six surfaces

## 9) Rollback Plan
- **Trigger:** Lookup discard incorrectly removes in-use provisional, System Settings save regression, contracts/HSEQ misroute returns
- **Owner:** Platform / Admin lane owner
- **Steps:** Revert squash merge; redeploy prior SHA

## 10) Evidence Pack
- CI run(s): (filled by CI on this PR)
- Base branch: `main`
- Local: targeted vitest + `tests/unit/test_safety_lookup_reject.py`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Admin/Platform allowlist respected (Analytics and other lanes untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Prod bake / smoke (conveyor)
- [x] **Gate 5:** Production verification plan ready

## 6b) Residual / deferred (Lane 6 remainder)
| ID | Severity | Why deferred |
|----|----------|--------------|
| PX-212 | P1 | Quarantine CAPA fields need asset-domain work beyond this slice |
| PX-271 | P1 | 2024 hours data correction is ops/data, not UI honesty |
| PX-275 | P1 | Engineer group seed cleanup is production data |
| PX-197 | P2 | Test Superuser accounts — ops hygiene |
| PX-239 | P2 | Workforce test roster rows — ops hygiene |
| PX-213/215/287 | P2/P3 | Already largely addressed on main (opaque ID hide / product honesty copy) |
| PX-180 | P2 | Auth redirect consistency needs dedicated routing pass |
| PX-184/214/240 | P2 | Workforce competency/training residual |
| PX-273 | P2 | Open HSEQ inbox questions — ops response, not code |
| PX-266 | P2 | Audit templates — conflict zone (Audits*) |

## Claimed vs residual

| Claimed | Residual / deferred |
|---------|---------------------|
| PX-274, PX-227, PX-228, PX-229, PX-196, PX-269, PX-186, PX-272, PX-161, PX-187 | PX-212, PX-271, PX-275, PX-197, PX-239, PX-180, PX-184, PX-214, PX-240, PX-273, PX-266, plus asset codename/GUID items already largely on main |

## Test plan
- [x] Targeted vitest (admin settings/lookups/forms/layout/notifications helpers)
- [x] `python3.11 -m pytest tests/unit/test_safety_lookup_reject.py`
- [ ] CI Frontend Tests + Backend unit suite on PR

Made with [Cursor](https://cursor.com)
