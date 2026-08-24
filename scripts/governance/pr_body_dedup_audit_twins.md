# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** FR-DEDUP-01 — governed hard purge of duplicate audit runs, plus a report-only duplicate scanner
- **User goal (1–2 lines):** The PROD Audit Status screen for Plantexpand Limited shows the same B2 audit three times. Remove the two re-imports completely, as if they had never existed, keeping the earlier audit that was subsequently updated — and find out where else this has happened.
- **In scope:**
  - `scripts/ops/run027/purge_duplicate_audit_runs.py` — hard-deletes explicitly named `audit_runs` rows and their full child closure.
  - `scripts/ops/run027/inventory_duplicate_registers.py` — report-only duplicate scan across the audit, risk, action and case registers.
  - `docs/ops/duplicate-audit-purge-runbook.md` — operator procedure with exact commands.
  - 42 unit tests against a real SQLite schema carrying production's `ON DELETE` rules.
- **Out of scope:**
  - **Executing the purge.** This PR ships the tooling. The authoring environment has no `DATABASE_URL` and no route to the production database; an operator with database access runs it per the runbook.
  - No purge script for the risk, action or case registers. The closure, dispositions and reference arithmetic here were reviewed for audits only.
  - No Alembic migration. None is needed — this is a data operation, not a schema change.
  - Layout, notification dispatcher and PlantEx Assist are untouched.
- **Feature flag / kill switch:** N/A — an ops script, not a runtime path. Its equivalent is that dry run is the default and `--apply` is opt-in, additionally gated by `--i-understand-prod` on a production-looking environment.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None. After the purge runs, the Audit Status screen shows the audit once instead of three times; no code change causes that.
- **Backend (handlers/services):** None. New code is confined to `scripts/ops/run027/`, which nothing imports.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** No migration, no model change. The scripts read reflected metadata and, on `--apply`, delete rows and append one `audit_log_entries` row.
- **Workflows/jobs/queues (if any):** None. Not wired into CI, deploy, or the conveyor.
- **Config/env/flags:** Reads `DATABASE_URL` (or `SQLALCHEMY_DATABASE_URI`), and `APP_ENV`/`ENVIRONMENT`/`QGP_ENV` to detect production.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive. Three new files plus tests; no existing file modified.
- **Tolerant reader / strict writer applied?** Yes. Every fact is reflected from the database the script is pointed at rather than read from the model files, because this repository has documented model/schema drift and `ondelete` is database-side behaviour. A missing table or a missing column is a normal answer that gets reported, not an exception.
- **Breaking changes:** None to the codebase. The *data* change is intentionally irreversible — see Rollback.
- **Migration plan:** No schema migration. The data operation is the runbook: scan → dry run → review → apply → verify.
- **Rollback strategy (DB):** No schema change to roll back. The row deletion cannot be undone; recovery is PITR or reconstruction from the mandatory manifest.

### Why a cascade delete was not enough

Deleting the `audit_runs` row and letting the database do the rest looks sufficient — `audit_responses`, `audit_findings`, `external_audit_import_jobs` and `external_audit_import_drafts` are all `ON DELETE CASCADE`.

It fails. **`external_audit_records.audit_run_id` carries no `ondelete` clause**, so it is `NO ACTION`. On an imported audit — exactly what these two are — the cascade delete raises a foreign key violation and rolls back the whole transaction. `external_audit_records` also hangs off the *import job*, not off the audit run, so a one-level child sweep would not have found it either.

So the closure is walked transitively over reflected foreign keys and every row is deleted explicitly, children before parents, in a computed order.

### Discovery is not permission

Reflection supplies the graph. A reviewed, per-table disposition supplies the decision:

| Table | `ON DELETE` | Disposition |
|---|---|---|
| `audit_responses`, `audit_findings` | CASCADE | purge |
| `audit_finding_risks` | CASCADE | purge — junction only, the risk survives |
| `external_audit_import_jobs`, `external_audit_import_drafts` | CASCADE | purge |
| `external_audit_records` | **NO ACTION** | purge — blocks the operation otherwise |
| `job_cell_links` | SET NULL | **detach** — job data survives, link clears |

A referencing table with **no** disposition is a refusal, not a default. Both available defaults are unacceptable: treat it as purgeable and the script destroys records nobody classified; treat it as detachable and it silently leaves dangling references. Refusing means the next release that adds a table referencing `audit_runs` stops this script until somebody classifies it.

### The half that foreign keys cannot see

`notifications`, `assignments`, `audit_log_entries`, `ai_decision_logs`, `compliance_evidence_links`, `job_cell_links` (`kind="app"`) and `capa_actions` all address records by a type name and an id with **no constraint behind them**. A delete neither cascades nor fails — it just leaves them pointing at nothing. These tables are found by reflection (any `entity_type`/`entity_id` pair, plus `capa_actions.source_type`/`source_id`) and classified:

- **purge** — `notifications`, `assignments`. Delivery artefacts and work allocations that would 404.
- **retain** — `audit_log_entries`, `ai_decision_logs`. Outliving their subject is the point of them.
- **refuse** — `capa_actions`, `compliance_evidence_links`, `job_cell_links`. Governed records with their own reference numbers, owners and compliance meaning. A human repoints or withdraws them first.

### The audit trail is written, not tidied

`audit_log_entries` is an append-only hash chain. Deleting the entries about a purged audit would break verification for every entry written afterwards and destroy the only evidence the audit existed. So the purge **appends** an entry carrying the full pre-delete row contents, **in the same transaction as the deletes** — if the trail cannot be written, nothing is deleted. This inverts `run025/purge_tenant_orphan_rows`, which deliberately does not write to the trail because its rows belong to no tenant; these rows do, so the per-tenant chain is writable and the argument reverses.

### Refusals

Dry run is the default. On top of that, the purge refuses on: a reference that does not exist; a reference belonging to another tenant; **deleting a whole duplicate group** with no survivor; an unclassified referencing table; a governed soft-referencing record; **reference-number reuse or collision**; and `--apply` without `--manifest`. Each has an explicit override flag where an override is defensible, and none is silent.

The reference check matters more than it looks. `ReferenceNumberService` mints `max(MAX(suffix), COUNT(*)) + 1`, so deleting rows can only lower the next value. `AUD-2026-0048` is likely the highest audit reference for 2026, and the same arithmetic applies to the `FND` and `AIM` sequences of the findings and import jobs being deleted. A `REISSUE` is a quiet record-keeping failure; a `COLLISION` means nobody can raise an audit or a finding at all, because the columns are UNIQUE.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Given `--reference AUD-2026-0043 --reference AUD-2026-0048 --tenant-id 1`, the dry run lists the full child inventory — including `external_audit_records`, reached two levels down — and writes nothing.
- [x] **AC-02:** On `--apply`, both audits and all 14 rows in their closure are hard-deleted children-first; the earlier audit, its responses, the other 18 findings and the escalated risk survive.
- [x] **AC-03:** The purge appends exactly one correctly chained `audit_log_entries` row (`sequence` = tail + 1, `previous_hash` = tail's `entry_hash`, hash recomputed with the model's own `compute_hash`), and pre-existing entries about the purged findings are retained.
- [x] **AC-04:** If the trail entry cannot be written, the whole transaction rolls back and nothing is deleted.
- [x] **AC-05:** The purge refuses on a mistyped reference, a cross-tenant reference, no surviving duplicate, an unclassified referencing table, a CAPA raised from a doomed finding, reference reuse, `--apply` without `--manifest`, `--apply` without `--tenant-id`, and `--apply` on production without `--i-understand-prod`.
- [x] **AC-06:** The scanner groups the three audits, marks the group import-derived, reports registers it did **not** examine and why, and has no `--apply`.

## 5) Testing Evidence (link to runs)
- [x] Lint — `flake8 scripts/ops/run027/ tests/unit/test_run027_duplicate_audit_purge.py` clean; `black` and `isort` applied.
- [x] Typecheck — `mypy -p scripts.ops.run027` clean. (One pre-existing error remains in `scripts/ops/run021/_common.py`, untouched here; CI's `mypy` scope is `src/`.)
- [x] Build — N/A, no build artefact.
- [x] Unit tests — **42 passed** in `tests/unit/test_run027_duplicate_audit_purge.py`.
- [x] Integration tests — related suites re-run green: `test_run025_reviewed_debris_purge.py` + `test_tenant_orphan_remediation.py`, **119 passed**.
- [ ] Contract tests — N/A, no API surface.
- [ ] E2E Smoke — N/A, no runtime path. Post-purge verification is the runbook's step 4.

Every refusal is proved by constructing the condition and observing the refusal, against a real SQLite database whose DDL carries production's `ON DELETE` rules.

**One finding worth flagging:** the first version of the test schema declared its foreign keys inline (`col INTEGER REFERENCES parent(id) ON DELETE SET NULL`). SQLAlchemy's SQLite reflection only parses `ON DELETE` from *table-level* `FOREIGN KEY` constraints, so every rule reflected as `NO ACTION` and the tests that depend on the difference between CASCADE, SET NULL and NO ACTION were passing for the wrong reason. The DDL was rewritten with table-level constraints, and `test_the_fixture_really_reflects_the_ondelete_rules_it_claims_to` now pins the reflected values so the artefact cannot return silently. PostgreSQL reads these from the catalogue and was never affected.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Audit register integrity — a duplicate is removed and the surviving audit, its findings, responses and the risk escalated from a purged finding are all intact. Covered by `test_apply_removes_the_twins_and_their_children_and_leaves_the_survivor`.
- [x] **CUJ-02:** Audit trail integrity — the chain remains verifiable across the purge, records what was destroyed, and retains the pre-existing entries about the purged rows. Covered by `test_apply_appends_one_chained_trail_entry_describing_the_purge` and `test_the_trail_entry_hash_matches_the_models_own_computation`.
- [x] **CUJ-03:** Raising a new audit or finding still works afterwards — protected by the reference-collision refusal (`test_freeing_the_top_of_the_reference_sequence_is_refused_and_overridable`).

## 7) Observability & Ops
- **Logs:** Both scripts emit a structured report on stdout (`--json`) with human-readable lines otherwise; exit codes distinguish clean dry run (1), refusal (3), rolled-back apply (4) and success (0).
- **Metrics:** None added. This is a one-off remediation, not a recurring path.
- **Alerts:** None added.
- **Runbook updates:** [`docs/ops/duplicate-audit-purge-runbook.md`](docs/ops/duplicate-audit-purge-runbook.md) — child inventory, every refusal and what to do about it, exact commands for scan / dry run / apply / verify, and the rollback position.

Evidence for the eventual production run is the mandatory `--manifest` (every column of every row, captured pre-delete) plus the dry-run JSON, both attached to the change record, and the appended trail entry.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Merge is inert — no runtime code changes, so nothing to verify beyond CI. Optionally run step 1 (the read-only scanner) against staging to confirm it connects and reports.
- **Canary plan:** N/A. Not a runtime change; there is no traffic to shift.
- **Prod post-deploy checks:** Deploying this changes nothing observable. The purge is a separate, deliberate operator action after merge, following the runbook. Its verification is runbook step 4: re-running the purge refuses with "does not exist", the Audit Status screen shows one B2 audit at 97.7%, no orphaned children remain, and the trail carries the purge entry with the chain still valid.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** For the code — any CI failure. For the data operation — the dry run showing an unexpected blocker, an unexpected child row, or a `COLLISION` verdict in the reference arithmetic.
- **Rollback steps:**
  1. **Code:** revert this commit. Nothing imports `scripts/ops/run027/`, so the revert is inert and needs no coordination.
  2. **Before apply:** nothing to roll back. The dry run writes nothing, and the scanner cannot write at all.
  3. **During apply:** automatic. Deletes, soft-reference cleanup and the trail entry share one transaction, so any failure leaves the register exactly as it was — proved by `test_nothing_is_deleted_when_the_trail_cannot_be_written`.
  4. **After apply:** there is no rollback. The hard delete is the requirement. Recovery is a point-in-time restore to just before the apply, or manual reconstruction from the manifest. **The operator must confirm the PITR window covers the change before running step 3.**
- **Owner:** David Harris (@cgtqwmwkhp-rgb)

## 10) Evidence Pack (links)
- CI run(s): see the checks on this PR.
- Staging deploy evidence: N/A — no runtime change to deploy.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API, schema or UX contract touched
- [x] **Gate 2:** CI green (lint/type/build/tests) — 42 new unit tests pass; 119 related tests re-run green
- [ ] **Gate 3:** Staging verification complete (evidence linked) — inert on merge; optional read-only scan
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A, not a runtime change
- [x] **Gate 5:** Production verification plan + monitoring ready — runbook step 4

> **Not merged and not executed.** Per the request, this PR is opened for review only.
> The purge has **not** been run against production: the authoring environment has no
> `DATABASE_URL` and no route to the production database. Running it is a separate,
> deliberate operator action after merge, following the runbook.
