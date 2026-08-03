# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** C-24 Phase 1 — converge `soa_control_entries` with `SoAControlEntry` and take it off the `alembic check` exclusion register (#1526)
- **User goal (1–2 lines):** Make the SoA control-entry table readable through the ORM again — `select(SoAControlEntry)` raises `UndefinedColumn` on every Alembic-built database today — and remove the last table anywhere in the repository whose model declares a column the database does not have.
- **In scope:** `20260908_soa_align` (4 `ADD COLUMN`, 1 index, 1 FK, 1 varchar widen); `SoAControlEntry` absorbs the 6 columns the database already had; `soa_control_entries` removed from `_ALEMBIC_CHECK_EXCLUDED_TABLES` + governance inventory + drift baseline; `DEFERRED_ABSENT_COLUMNS` emptied; PX-255 scoring policy written down; N-1 grandfathering position written down
- **Out of scope:** The other 9 IMS / ISO27001 exclusion entries (same treatment, one owner decision each — #1526); collapsing `inclusion_justification` / `exclusion_justification` into `justification`, which is a data exercise for the IMS owner; row-level security on this table; backfilling `tenant_id`
- **Feature flag / kill switch:** N/A — schema convergence

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None. `SoAControlEntry` has no live read path; the import in `src/api/routes/iso27001.py` is dead
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None — no Pydantic schema exposes this model
- **Database (migrations/entities/indexes):** `alembic/versions/20260908_soa_align.py`. Adds `tenant_id` (nullable, FK `tenants.id`), `justification`, `implementation_method`, `risk_treatment_reference`; creates `ix_soa_control_entries_tenant_id`; widens `implementation_status` from `varchar(30)` to `varchar(50)`. **Drops nothing.**
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive in both directions. The database gains the four columns the model declared; the model gains the six the database had (`inclusion_justification`, `exclusion_justification`, `implementation_description`, `responsible_party`, `target_completion_date`, `updated_at`). Neither side loses anything.
- **Tolerant reader / strict writer applied?** Yes. The new columns arrive NULL and are never populated by inference. `justification` sits *beside* `inclusion_justification` and `exclusion_justification` rather than being filled from either — which of the two the model's single column means is an IMS domain question, and guessing it would file an exclusion rationale as an inclusion rationale on live certification evidence (#1398 principle). The alternative autogenerate offered was six `DropColumnOp` over that evidence.
- **Breaking changes:** None. The one behavioural change is that the model now declares the `ON DELETE CASCADE` the physical `control_id` foreign key has carried since `20260120_add_iso27001_isms`; the constraint itself is untouched.
- **Migration plan:** `alembic upgrade head`. Idempotent — each column is skipped if present, the index is skipped if present, the widen is skipped unless the column is still `varchar(30)`. A table that is absent is skipped with a log line.
- **Rollback strategy (DB):** `alembic downgrade -1` drops the four columns and the index and narrows `implementation_status` back. The four are created empty, so this is lossless at the point a downgrade is plausible. The narrow **refuses** (`StatusValuesTooLongError`) rather than truncating a status longer than 30 characters.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `select(SoAControlEntry)` succeeds against a migration-built database. Verified: it raises `UndefinedColumnError: column soa_control_entries.tenant_id does not exist` at `20260907_ims_unification` and returns rows at `20260908_soa_align`.
- [x] AC-02: `soa_control_entries` produces **zero** autogenerate operations. Verified: 15 operations before (`AddColumnOp` 4, `DropColumnOp` 6, `AlterColumnOp` 1, `CreateForeignKeyOp` 2, `CreateIndexOp` 1, `DropConstraintOp` 1), 0 after, on an unfiltered comparison with `include_object` allowing everything.
- [x] AC-03: The name is removed from `_ALEMBIC_CHECK_EXCLUDED_TABLES` and from `docs/governance/alembic_check_excluded_tables.md` in the same PR, and `alembic check` is green without it.
- [x] AC-04: `AddColumnOp` is now **0 across the whole repository**, excluded tables included — the zero-tolerance rule in `scripts/validate_alembic_drift_ratchet.py` now defers nothing at all.
- [x] AC-05: `DEFERRED_ABSENT_COLUMNS` is empty and `tests/unit/test_run026_deferral_register.py` pins it empty, which is the strongest that assertion has ever been.
- [x] AC-06: No other table's drift moved. Verified per table: exactly one entry differs between the before and after censuses.
- [x] AC-07: PX-255 policy and the N-1 grandfathering position are written down under `docs/governance/`.

## 5) Testing Evidence (link to runs)
- [x] Lint — `black --check`, `isort --check-only`, `flake8` clean on every changed `src/` and `tests/` file
- [x] Typecheck — `mypy src/domain/models/iso27001.py`: no issues
- [x] Build — N/A
- [x] Unit tests — **5044 passed, 8 skipped, 0 failed** (`tests/unit`). One test failed on the first run and was corrected, not weakened: `test_delete_cascade_audit_visibility` detected `("iso27001_controls", "soa_control_entries")` as a database-level cascade with no audit coverage. It is not a new cascade — the constraint has been `ON DELETE CASCADE` since 2026-01-20 and the census could not see it because the model under-declared it. The pair is now recorded in `CASCADES_INVISIBLE_TO_AN_ORM_HOOK`, which is exactly what that test's docstring asks for.
- [x] Integration tests — PostgreSQL 16.14, `alembic upgrade head` from empty: upgrade, `downgrade -1`, re-upgrade, and upgrade over a table where `tenant_id` was already present (the adopt path) all clean
- [ ] Contract tests (if applicable) — N/A, no API surface
- [ ] E2E Smoke (critical journeys) — N/A, no read or write path touches this table

Measured on PostgreSQL 16.14 against a database built by `alembic upgrade head`:

| | main | this PR |
| --- | --- | --- |
| `before_filter` operations / tables | 1058 / 209 | 1058 / 209 |
| drift hidden by `include_object` | 182 / 18 tables | 167 / 17 tables |
| `AddColumnOp` anywhere | 4 | **0** |
| `audit_attribution_schema` deferred columns | 4 | **0** |
| `audit_attribution_schema` database-only columns | 92 | 86 |
| ratchet exit code | 0 | 0 |

`before_filter` being *unchanged* is the point: the table joined the comparison and contributed nothing, the same result `20260906_doc_ctl_children` and `20260907_ims_unification` produced.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `alembic upgrade head` on an empty PostgreSQL 16 database completes and reports the four columns added
- [x] CUJ-02: `alembic check` under `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` reports "No new upgrade operations detected" with the name gone from the frozenset
- [x] CUJ-03: `scripts/validate_alembic_drift_ratchet.py --database-url ...` exits 0, reports 0 `AddColumnOp`, and `exclusions with no drift left (removable): []`
- [x] CUJ-04: `scripts/ops/run026/audit_attribution_schema.py` reports 0 absent columns, 0 deferred, 0 failures

## 7) Observability & Ops
- **Logs:** The migration logs how many columns it added, how many it adopted unverified, and the resulting `implementation_status` length, at `alembic.runtime.migration`
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** `docs/governance/alembic_check_excluded_tables.md` (dated 2026-09-08 section), `docs/governance/attribution_schema_drift.md`, plus two new notes: `docs/governance/uvdb_qualification_scoring_policy.md` (PX-255) and `docs/governance/n1_closed_cases_grandfathering.md` (N-1 / PX-333)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Run `alembic upgrade head`, then `scripts/ops/run026/audit_attribution_schema.py --json` and confirm `absent_columns_total` is 0. The table is expected to be empty or near-empty; confirm the row count before and after is unchanged.
- **Canary plan:** N/A — no runtime surface
- **Prod post-deploy checks:** Same census. Note that production's physical schema was **not** reachable for this work: everything here is measured against a database built by this repository's own migration chain. This migration is a structural `ADD COLUMN`, not a data-conditional one, so it is expected to hold — but that is an inference, and the census is what confirms it.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** `alembic upgrade head` fails on an environment, or the census reports something unexpected on this table after deploy
- **Rollback steps:** `alembic downgrade 20260907_ims_unification`, then revert the PR. The downgrade drops only what the upgrade created. If it refuses with `StatusValuesTooLongError`, some row holds an `implementation_status` longer than 30 characters written since the upgrade — decide what that value should be rather than letting it be truncated.
- **Owner:** Platform / DBA, with IMS / ISO27001 for the justification-column question

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: To follow
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API or UX surface; the data decision (database authoritative, drop nothing, do not infer the justification mapping) is recorded in `docs/governance/attribution_schema_drift.md`
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — census command in §8
