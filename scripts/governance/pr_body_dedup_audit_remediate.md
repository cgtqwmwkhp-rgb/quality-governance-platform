# Change Ledger (CL-DEDUP-01-REMEDIATE)

## 1) Summary
- **Feature / Change name:** FR-DEDUP-01 follow-up — governed CEL remap, CAPA reassign, and `--survivor-reference` so PROD apply can clear exit-3 blockers
- **User goal (1–2 lines):** The PROD dry-run for `AUD-2026-0043` / `AUD-2026-0048` refused apply (exit 3) on 970 compliance evidence links, 10 CAPAs, and a no-survivor identity mismatch for 0048. Make a clean governed dry-run/apply possible without weakening default refusals.
- **In scope:**
  - `scripts/ops/run027/_remediate.py` — finding matching, CEL remap/soft-withdraw, CAPA reassign, survivor authorisation/corroboration
  - Flags on `purge_duplicate_audit_runs.py`: `--survivor-reference`, `--remap-evidence-links`, `--expect-evidence-links`, `--withdraw-unmappable-evidence`, `--reassign-capa-to-survivor`, `--expect-capa-action`
  - Soft-link blocker deferral (disposition stays `refuse`; never reclassified to `purge`)
  - Runbook §1a documenting blockers A/B/C and the remediation command block
  - Unit tests for the new behaviour (61 total in the suite)
- **Out of scope:**
  - **Executing `--apply` against PROD.** This PR ships tooling only.
  - CAPA schema migration / `withdrawn` status (no honest withdraw value exists today)
  - `job_cell_links` `kind="app"` remediation; risk-register withdrawal; scanner identity changes
  - Layout / notification / Assist surfaces
- **Feature flag / kill switch:** N/A — ops script. Default remains refuse; remediation is opt-in via explicit flags.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** None. Changes confined to `scripts/ops/run027/` and tests/docs.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** No migration. On `--apply` with remediation flags: UPDATEs to `compliance_evidence_links` / `capa_actions`, then existing deletes + trail append.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** Same `DATABASE_URL` / prod detection as FR-DEDUP-01.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive flags and a new helper module. With no new flags, soft-link refusals are byte-identical to FR-DEDUP-01 (regression-tested).
- **Tolerant reader / strict writer applied?** Yes. Columns reflected; finding match columns intersected; CEL soft-delete only if `deleted_at` exists.
- **Breaking changes:** None to the codebase. Data operation remains irreversible for deletes; CEL/CAPA UPDATEs reversible from manifest `remediation_pre_update_rows`.
- **Migration plan:** No schema migration. Operator path: scan → dry run with remediation flags → review → apply → verify.
- **Rollback strategy (DB):** Deletes → PITR/manifest rebuild. Remediation UPDATEs → restore from manifest pre-update rows.

### Approaches chosen for the three PROD blockers

| Blocker | Approach |
|---|---|
| A — 970 CEL | `--remap-evidence-links` + `--expect-evidence-links N` (+ optional `--withdraw-unmappable-evidence`). Remap `entity_id` to matched survivor finding; soft-delete when redundant or unmappable. |
| B — 10 CAPA | `--reassign-capa-to-survivor` + exact `--expect-capa-action` id set. Updates `source_id` only. **No CAPA withdraw** in this script. |
| C — 0048 no survivor | `--survivor-reference` authorises + corroborates (lifecycle columns ignored for corroboration only). Scanner/`REGISTERS` identity unchanged. |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Without remediation flags, CEL and CAPA soft hits still refuse with `must-not-touch` (deferral does not drop refusals).
- [x] **AC-02:** `--remap-evidence-links` requires `--survivor-reference` and exact `--expect-evidence-links`; remaps to matched survivor findings; withdraws redundant/unmappable as designed.
- [x] **AC-03:** `--reassign-capa-to-survivor` requires exact `--expect-capa-action` set; reassigns `source_id`; converging CAPAs refuse; unmappable CAPA has no override.
- [x] **AC-04:** `--survivor-reference` clears lifecycle-diverged no-survivor without `--allow-no-survivor`; bad/cross-tenant/self survivor is not rescued by `--allow-no-survivor`.
- [x] **AC-05:** Remediation appears in trail `new_values` and is hash-covered; runbook documents blockers A/B/C.
- [x] **AC-06:** `REGISTERS` audit identity still includes `status` and `score_percentage`.

## 5) Testing Evidence (link to runs)
- [x] Lint — `flake8` / `black` / `isort` on `scripts/ops/run027/` + test file.
- [x] Typecheck — `mypy -p scripts.ops.run027` clean for run027 (pre-existing `run021/_common.py` error untouched).
- [x] Build — N/A.
- [x] Unit tests — **61 passed** in `tests/unit/test_run027_duplicate_audit_purge.py`.
- [ ] Contract / E2E — N/A; no runtime path. PROD apply remains a separate operator action.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Duplicate purge with CEL remap leaves survivor coverage intact (remap + redundant withdraw).
- [x] **CUJ-02:** CAPA provenance preserved under reassignment (`reference_number`/status unchanged; `source_id` updated).
- [x] **CUJ-03:** Audit trail remains verifiable with remediation in `new_values`.

## 7) Observability & Ops
- **Logs:** Dry-run/apply JSON gains `remediation` (matches, evidence dispositions, CAPA reassigns). Exit codes unchanged.
- **Metrics / Alerts:** None.
- **Runbook updates:** [`docs/ops/duplicate-audit-purge-runbook.md`](docs/ops/duplicate-audit-purge-runbook.md) — §1a blockers A/B/C, corrected PROD facts, remediation command blocks.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Merge is inert for runtime. Optional read-only dry-run against staging.
- **Canary plan:** N/A.
- **Prod post-deploy checks:** Deploying this changes nothing observable. Operator apply follows the runbook after a clean dry run. **This PR does not run `--apply` against PROD.**

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CI failure for the code; unexpected dry-run blockers or match diagnostics for the data op.
- **Rollback steps:**
  1. **Code:** revert this commit — nothing imports run027 from runtime paths.
  2. **Before apply:** nothing to roll back.
  3. **During apply:** single transaction; failure → exit 4, register unchanged.
  4. **After apply:** deletes → PITR/manifest; CEL/CAPA UPDATEs → restore from `remediation_pre_update_rows`.
- **Owner:** David Harris (@cgtqwmwkhp-rgb)

## 10) Evidence Pack (links)
- CI run(s): see the checks on this PR.
- Staging deploy evidence: N/A — no runtime change to deploy.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API/schema/UX contract touched
- [x] **Gate 2:** CI green (lint/type/build/tests) — 61 unit tests pass locally
- [ ] **Gate 3:** Staging verification complete (evidence linked) — inert on merge; optional dry-run
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — runbook step 4

> **Not executed against PROD.** Per the request, `--apply` was not run against production.
> Opening for review so a subsequent operator dry-run can clear blockers A/B/C under governance.
