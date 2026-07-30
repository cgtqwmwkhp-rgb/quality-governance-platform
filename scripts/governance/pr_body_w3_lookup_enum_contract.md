# Change Ledger (CL-W3-LOOKUP-ENUM-CONTRACT)

## 1) Summary
- **Feature / Change name:** Wave 3 start — durable Lookup ↔ enum contract (`w2-enum-contract`) + admin write guard (`w4-lookup-admin` / R22-03)
- **User goal (1–2 lines):** Keep every active enum-backed lookup option submittable, and stop admins from recreating the PX-281/282 drift via Lookup Tables.
- **In scope:** Clear stale write-contract baseline gaps for `complaint_types` / `incident_types` (fixed in #1385); add `ensure_enum_backed_code` admin write guard on create/update; unit + integration + discovery self-checks tying `lookup_enum_contract` to write-contract Guard 3
- **Out of scope:** `severity_levels` product decision (`negligible` still mismatches complaint priority / near-miss potential_severity); B-10 forbid campaign; ownership / audit census / investigation PRs; deploy config
- **Feature flag / kill switch:** N/A — validation + test baseline only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `lookup_enum_contract.ensure_enum_backed_code`; `FormConfigService` create/update lookup option calls it
- **APIs (endpoints changed/added):** `POST`/`PATCH /api/v1/admin/config/lookup/{category}` now 422 when category is enum-backed and `code` is outside the paired enum (allowed values named in the error)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Strict writer for enum-backed categories only; free-form categories (`customers`, `workforce_roles`, …) unchanged
- **Tolerant reader / strict writer applied?** Yes — admin cannot write a code the case create enums would reject
- **Breaking changes:** An admin who previously could save a non-enum code on `complaint_types` / `incident_types` now gets 422 (those codes were already unusable on case submit)
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Seeded `complaint_types` / `incident_types` have **no** entries in `KNOWN_LOOKUP_ENUM_GAPS` (write-contract Guard 3 enforces them green)
- [x] AC-02: Discovery self-check fails if any enum-backed category is re-recorded in the baseline
- [x] AC-03: Admin `POST` of `complaint_types` / `workmanship` returns 422 naming allowed codes
- [x] AC-04: Admin `POST` of an enum member (e.g. `service`) still succeeds
- [x] AC-05: Free-form categories remain unconstrained
- [x] AC-06: Residual `severity_levels` → `negligible` gaps remain recorded (not silently dropped)
- [x] AC-07: Existing integration contract probes (active option → case create 201) unchanged in intent

## 5) Testing Evidence (link to runs)
- [x] Lint — black + isort on touched modules
- [x] Typecheck — N/A for thin validation helper + tests
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_lookup_enum_contract.py`, `tests/unit/test_form_config_service.py::TestLookupOptions` (local pass)
- [x] Contract tests — `TestLookupEnumAgreement` + `TestDiscoveryIsNotVacuous` (31 passed, 2 xfailed = residual severity)
- [ ] Integration tests — admin rogue-create probe added; CI linked after open
- [ ] E2E Smoke — N/A for this slice

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Complaint / incident forms still offer only enum-valid active options (seed + Guard 3)
- [x] CUJ-02: Admin Lookup Tables cannot add a code that would 422 on case create for enum-backed categories
- [x] CUJ-03: Free-form lookup create (e.g. customers / ad-hoc categories) still works
- [x] CUJ-04: Severity residual documented — `negligible` still xfailed for complaint priority / near-miss potential_severity pending product decision

## 7) Observability & Ops
- **Logs:** Domain `ValidationError` on reject (existing exception → HTTP envelope)
- **Metrics:** Existing `form_config.mutation` only on successful writes
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Admin Lookup Tables — add valid `complaint_types` code succeeds; add `workmanship` → 422; complaint/incident create still 201 for offered options
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Lookup Tables create on `complaint_types` / `incident_types`; confirm free-form categories still editable

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Legitimate admin workflow blocked on a code that should be allowed (enum member rejected) or free-form category incorrectly constrained
- **Rollback steps:** Revert this PR (restores prior admin write behaviour + prior baseline entries)
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A until merge
- Canary evidence (if applicable): N/A
- Local evidence: `pytest` unit/contract slice — 31 passed, 2 xfailed (severity residual)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — enum-backed admin write strictness; free-form unchanged
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A pre-merge; validation-only
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — spot-check plan above

## Board closure notes
- **w2-enum-contract:** Durable assertion path complete for clean 1:1 pairings (`complaint_types`, `incident_types`) — seed, write-contract Guard 3 (no stale xfail), integration probes, discovery ratchet.
- **w4-lookup-admin (R22-03):** Included — admin create/update rejects non-enum codes for `ENUM_BACKED_LOOKUPS` (recommended follow-up from #1385).
- **Not closed here:** `severity_levels` multi-field / `negligible` product decision.
