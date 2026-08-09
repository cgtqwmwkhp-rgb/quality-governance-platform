# Change Ledger (CL-LIB-WA2-DOCKER-FUNCTIONS-JSON)

## 1) Summary
- **Feature / Change name:** Ship `functions.json` in the production image so WA-2 migration can seed
- **User goal (1–2 lines):** Staging/prod `alembic upgrade` for WA-2 succeeds; `document_functions` seed is not FileNotFound in ACI.
- **In scope:** Dockerfile COPY of `specs/governance-library/functions.json`; unit pin that the COPY stays present
- **Out of scope:** Changing the migration seed strategy; FE; further Library slices
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None (image contents only)
- **APIs:** None
- **Database:** Unblocks already-merged `20261025_lib_wa2_functions_pel` on STG/PROD
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** `tests/unit/test_dockerfile_library_specs.py`
- **Docs:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive image file only; no API/schema change
- **Breaking changes:** None
- **Migration plan:** None in this PR — re-run governed Staging/Prod deploy on tip after merge
- **Rollback strategy (DB):** N/A

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Deploy migration integrity | WA-2 migration failed in ACI (`functions.json` missing) while tip CI was green | Image includes the seed file; unit pin prevents silent regression |
| Enhance ≠ replicate | — | Same seed file the migration already reads; no second seed source |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Dockerfile copies `specs/governance-library/functions.json` into the image
- [x] AC-02: Unit test fails if that COPY is removed
- [ ] AC-03: Staging deploy on tip succeeds through `alembic upgrade head` and STG build_sha matches tip

## 5) Testing Evidence (link to runs)
- [x] Local unit pin added
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Root cause of STG fail = missing COPY (not migration logic)
- [ ] CUJ-02: Post-merge STG migration completes; PROD follows; healthz 200 on tip SHA

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None
- **Runbook updates:** None — governed re-deploy after merge

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Merge → tip CI → Deploy Staging → Deploy Production → verify build_sha
- **DONE bar:** MAIN tip = STG = PROD + healthz 200

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Image build failure unique to this COPY
- **Rollback steps:** Revert this PR; tip remains on prior image (WA-2 code still on main but STG/PROD stay on pre-WA-2 until fixed)
- **Data repair:** None

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: After merge tip chase (re-run WA-2 migration)
- Canary evidence (if applicable): N/A
- Acceptance notes: Root cause was Dockerfile omitting `functions.json` while migration seeds from it in ACI

## 11) Post-Release Monitoring
- Staging/Prod deploy green; `/api/v1/meta/version` build_sha = tip; healthz 200

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — image COPY only; no twin seed source
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge; migration must pass
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE before DONE
