# Change Ledger (CL-B10-W4-EXTRA-FORBID)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — write-schema `extra="forbid"` inventory lock / ratchet
- **User goal (1–2 lines):** Stop the bleed of write request bodies that silently ignore unknown fields by pinning forbid/open counts from `origin/main`, without converting all 294 open schemas in this PR.
- **In scope:** Inventory script; committed baseline JSON; Markdown inventory; CI step on `schema-constraint-lint`; unit tests for ratchet failure/warn paths; this Change Ledger
- **Out of scope:** Mass conversion of 294 open schemas; edits to `KNOWN_LAX_WRITE_SCHEMAS` allowlist; new `extra="forbid"` conversions beyond what main already has (`ActionCreate` / `ActionUpdate`)
- **Feature flag / kill switch:** N/A — CI policy only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None at runtime. Policy artifacts under `docs/governance/`; discovery reuses OpenAPI write-operation inventory
- **Database (migrations/entities/indexes):** No migrations
- **Workflows/jobs/queues (if any):** `.github/workflows/ci.yml` — new step on `schema-constraint-lint`
- **Config/env/flags:** None (script seeds minimal CI env for `app.openapi()` import only)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — existing open schemas grandfathered at a pinned ceiling; forbid set is a floor; converting open→forbid is encouraged and only requires a baseline refresh
- **Breaking changes:** None for runtime. CI fails if forbid coverage shrinks or open write schemas grow above baseline
- **Migration plan:** None. Follow-up PRs convert schemas one-by-one and refresh `write_schema_extra_forbid_baseline.json`
- **Rollback strategy (DB):** No DB change — revert commit / remove CI step

## 4) Acceptance Criteria (AC)
- [x] AC-01: Inventory enumerates OpenAPI write/input schemas and counts `extra="forbid"` vs open (`docs/governance/write_schema_extra_forbid_inventory.md`)
- [x] AC-02: Committed baseline pins floor/ceiling measured from `origin/main` — **forbid ≥ 2**, **open ≤ 294**, total **296** (`docs/governance/write_schema_extra_forbid_baseline.json`)
- [x] AC-03: CI lint `scripts/validate_write_schema_extra_forbid_ratchet.py` fails when forbid count decreases, open count increases above baseline, or a baseline forbid schema loses forbid
- [x] AC-04: `KNOWN_LAX_WRITE_SCHEMAS` allowlist is **not** modified
- [x] AC-05: Unit tests cover pass path, open-growth failure, forbid-shrink / membership-swap failure, and improvement warnings

## 5) Testing Evidence (link to runs)
- [x] Lint — local ratchet script green against generated baseline
- [x] Typecheck — N/A for scripts/docs
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_write_schema_extra_forbid_ratchet.py`
- [ ] Integration tests — N/A (no runtime/DB change)
- [ ] Contract tests (if applicable) — existing Guard 2 unchanged; allowlist untouched
- [ ] E2E Smoke (critical journeys) — N/A for policy-only change; CI run linked after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Schema-constraint CI job runs the extra=forbid ratchet without false positives on current OpenAPI inventory (2 forbid / 294 open)
- [x] CUJ-02: Synthetic open-count increase and forbid-membership loss are rejected by unit tests / ratchet logic

## 7) Observability & Ops
- **Logs:** Script prints forbid/open counts and `[FAIL]`/`[WARN]` lines in CI
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** `docs/governance/write_schema_extra_forbid_inventory.md` (refresh via `--write-baseline`)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** N/A — docs + CI only; no deploy-time schema change
- **Canary plan:** N/A
- **Prod post-deploy checks:** N/A

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CI lint false-positive blocking legitimate new write schemas that correctly declare `extra="forbid"`, or discovery breakage
- **Rollback steps:** Revert this PR (or temporarily remove the CI step / refresh baseline with review if the inventory genuinely changed)
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — policy/docs only; no runtime contract change
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — N/A policy-only
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — N/A runtime

## Measured baseline (`origin/main`)
| Metric | Value |
| --- | ---: |
| Distinct write schemas | 296 |
| `extra="forbid"` | 2 (`ActionCreate`, `ActionUpdate`) |
| Open (non-forbid) | 294 |
| Write operations | 314 |
