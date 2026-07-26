# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Run021 Wave 2 — portal/API honesty (PX-281 backend, PX-294, PX-302, PX-328)
- **User goal (1–2 lines):** Portal and integration callers should not receive spurious HTTP 422s for realistic contact values; employees should see decoded report text, honest contact-field semantics, and actionable microphone errors.
- **In scope:** `QuickReportCreate` limits + contact normalisation; complaint/incident DB-safe clipping; `PortalTrack` entity decode; incident `person_contact` field semantics; voice-error surfacing in `DynamicFormRenderer`; aligned frontend phone limit (50); unit/vitest coverage; this Change Ledger
- **Out of scope:** PX-327 upload transport; PX-300/PX-282 (merged in #1297/#1324); PX-306 migration (already on main); PX-252 Audit Pack; #1307
- **Feature flag / kill switch:** None — revert this PR

## 2) Impact Map (what changed)
- **Backend:** `src/api/routes/employee_portal.py` — raise `reporter_phone`/`reporter_name`/`location` limits; email-in-phone normalisation; complaint phone + incident location clipping to DB columns
- **Frontend:** `PortalDynamicForm.tsx` (phone limit 50, PX-302 contact field); `PortalTrack.tsx` (PX-294 decode); `DynamicFormRenderer.tsx` (PX-328 voice errors + mic labels)
- **APIs:** `POST /api/v1/portal/reports/` accepts email-shaped values in `reporter_phone` (normalised server-side) and phones up to 50 chars
- **Schemas:** `QuickReportCreate` max lengths updated; tolerant contact normalisation validator added
- **Database:** No migration — persistence clipped to existing column widths (complaint phone 30, incident location 300)
- **Tests:** `tests/unit/test_portal_intake_field_limits.py`; vitest updates + `PortalTrack.test.tsx`, `DynamicFormRenderer.voice.test.tsx`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive/tolerant — legacy callers sending email in `reporter_phone` are normalised instead of 422
- **Tolerant reader / strict writer applied?** Yes — API accepts then routes contact data; DB writes respect column limits; full values remain in `reporter_submission` snapshot
- **Breaking changes:** None — stricter clients unaffected; looser payloads now succeed
- **Migration plan:** N/A
- **Rollback strategy:** Revert merge; no data rewrite required

## 4) Acceptance Criteria (AC)
- [x] AC-01: Email in `reporter_phone` no longer 422 — routed to `reporter_email` on `QuickReportCreate`
- [x] AC-02: `reporter_phone` API max is 50 (near_miss column); complaint persist clips to 30 without DB error
- [x] AC-03: Incident location clipped to 300 chars at persist; API accepts up to 500
- [x] AC-04: Portal Track decodes `&amp;` in title/timeline/next steps (PX-294)
- [x] AC-05: Incident dynamic form no longer prefills email into a tel/contact-number field (PX-302)
- [x] AC-06: Denied microphone permission surfaces field-level error (PX-328)
- [x] AC-07: Frontend `REPORTER_PHONE_MAX_LENGTH` matches backend (50)

## 5) Testing Evidence (link to runs)
- [x] Unit — `pytest tests/unit/test_portal_intake_field_limits.py`
- [x] Vitest — portal payload, PortalTrack, DynamicFormRenderer voice
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Complaint/API submission with long work email via `reporter_phone` succeeds
- [x] CUJ-02: Track detail shows `Health & Safety` not `Health &amp; Safety`
- [x] CUJ-03: Mic denied → visible error under textarea field

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Submit complaint via API with email in `reporter_phone`; open Track detail with `&` in title; deny mic on portal textarea
- **Canary plan:** Full promote after CI green
- **Prod post-deploy checks:** Same three checks on purple-water

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Portal submit regressions; contact data mis-routed
- **Rollback steps:** Revert PR merge
- **Owner:** Platform engineering

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main`
- Depends on: Wave 1 portal frontend (#1297) for client-side PX-281 routing

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — limits aligned to DB; normalisation documented
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
