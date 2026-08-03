# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** C-24 Phase 2 — converge the last nine IMS / ISO27001 tables with their models and empty that group off the `alembic check` exclusion register (#1526)
- **User goal (1–2 lines):** Make 50 columns of live ISO 27001 evidence visible to the ORM that declares the tables holding it, and stop `include_object` hiding 144 autogenerate operations on nine tables that every ISO 27001 endpoint reads and writes.
- **In scope:** `20260909_iso_absorb` (16 `varchar` widenings, 7 `ADD CONSTRAINT ... FOREIGN KEY`, 1 table comment — **no `ADD COLUMN`, no `DROP COLUMN`, no `DROP CONSTRAINT`**); `src/domain/models/iso27001.py` and `src/domain/models/ims_unification.py` absorb 50 database-only columns, record 25 nullability facts, adopt `jsonb` on 8 columns, declare 9 `ON DELETE SET NULL` options, 14 indexes and 1 unique constraint; all nine names removed from `_ALEMBIC_CHECK_EXCLUDED_TABLES`, the governance inventory and the drift baseline
- **Out of scope:** The eight junction / config entries that remain on the register — they are tables with no model (`DropTableOp`) and one model whose table has a different name (`CreateTableOp`), a different problem with a different fix; deciding which of the six duplicated column pairs supersedes the other (`plan_name`/`name`, `resource_name`/`system_name`, `findings`/`findings_details`, …), which is an IMS data exercise; enforcing any of the 25 nullability claims in the database; row-level security on these tables; the two stale `complaints` / `incidents` baseline rows
- **Feature flag / kill switch:** N/A — schema convergence
- **Stacks on:** #1530 (`fix/c24-soa-align-1526`, `20260908_soa_align`). Merge that first.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None. No handler or service was edited. `src/api/routes/iso27001.py` reads and writes seven of these nine tables and is unchanged; the six absorbed `NOT NULL` columns carry the server default the database already had, so the ORM still omits them from `INSERT` and the database still supplies the value
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None. The request schemas (`AccessControlCreate`, `BCPCreate`, `SupplierAssessmentCreate`, `SecurityIncidentCreate`) are untouched, which matters because they are where the requiredness of `granted_date`, `scope`, `rto_hours` and the rest is actually enforced
- **Database (migrations/entities/indexes):** `alembic/versions/20260909_iso_absorb.py`. Widens 16 `varchar` columns (catalogue-only in PostgreSQL); creates 7 foreign keys to `users.id`, all `ON DELETE SET NULL`; sets the `iso27001_controls` table comment. **Adds no column, drops nothing, creates no index.**
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** The rule from Phase 1 — *the side that moves is the side whose move cannot lose or reject data* — applied per class of disagreement. That puts almost all of the movement on the models: they absorb the 50 columns the database has, record the 25 nullability facts the database enforces, adopt `jsonb`, and declare the `ON DELETE SET NULL`, indexes and unique constraint that already exist. The database moves only where the model was the wider of the two (16 `varchar` widenings) or where the model declared a constraint that was simply absent (7 foreign keys).
- **Tolerant reader / strict writer applied?** Yes. Six of the absorbed columns sit beside a later column that might have been meant to replace them — `plan_name` beside `name`, `plan_type`, `status`, `resource_name` beside `system_name`, `findings` beside `findings_details`, `notification_required` beside `regulatory_notification_required`. `20260407_iso27001_drift_02` added the later one *beside* the original rather than migrating the data across, so both are kept and neither is inferred from the other. Choosing between them is a decision about live certification evidence, and a migration does not invent compliance evidence (#1398). The alternative autogenerate offered was 50 `DropColumnOp` over that evidence.
- **Breaking changes:** None at runtime. Two behavioural notes: (1) 25 model columns move from `nullable=False` to `nullable=True`, which records what the database has permitted since 2026-04-07 — SQLAlchemy never enforced the stricter claim, the read paths already null-guard these fields (`r.granted_date.isoformat() if r.granted_date else None`), and the request schemas still reject a missing value. (2) Deleting a `users` row now nulls seven columns that previously kept a dangling id; the `_name` column beside each one keeps the recorded name.
- **Migration plan:** `alembic upgrade head`. Idempotent — a widen is skipped unless the column is still at the old length, a foreign key is skipped if one already exists on that column, the comment is set unconditionally. A table that is absent is skipped with a log line. The foreign-key step **refuses** (`OrphanedReferenceError`) if any of the seven columns holds an id no `users` row has: nulling it would discard the only machine-readable link that row has to a person, and creating the constraint `NOT VALID` would reflect as a real foreign key, so the next `alembic check` would call the drift resolved when it is not.
- **Rollback strategy (DB):** `alembic downgrade -1` narrows the 16 columns back, drops the 7 foreign keys and removes the comment. The narrowing **refuses** (`ValuesTooLongError`) rather than truncate a value written since the widen.

## 4) Acceptance Criteria (AC)
- [x] AC-01: All nine tables produce **zero** autogenerate operations. Verified on an unfiltered comparison with `include_object` allowing everything: 144 before (`AlterColumnOp` 49, `DropColumnOp` 50, `CreateForeignKeyOp` 16, `DropIndexOp` 14, `DropConstraintOp` 9, `CreateTableCommentOp` 1), **0** after.
- [x] AC-02: No `DropColumnOp` was executed and no `ADD COLUMN` was needed. The migration contains no `op.drop_column` and no `op.add_column`.
- [x] AC-03: The nine names are removed from `_ALEMBIC_CHECK_EXCLUDED_TABLES`, from `docs/governance/alembic_check_excluded_tables.md` and from `alembic_drift_baseline.json` in the same PR, and `alembic check` is green without them.
- [x] AC-04: `AddColumnOp` stays at **0** across the whole repository, excluded tables included.
- [x] AC-05: No other table's drift moved. `before_filter` is unchanged at 1058 operations across 209 tables, and the fully unfiltered census falls from 1225 across 226 to 1081 across 217 — exactly the 144 operations and 9 tables removed here.
- [x] AC-06: The ORM write path still works on all six absorbed `NOT NULL` columns. Verified by inserting a row into each of the five written tables through the ORM and reading back `resource_type='system'`, `resource_name=''`, `plan_name=''`, `plan_type='continuity'`, `status='draft'`, `notification_required=False` — supplied by the database, not by SQLAlchemy.
- [x] AC-07: The models still build on SQLite, which `tests/integration/conftest.py` falls back to. Verified: `CreateTable` + insert for all seven ISO 27001 tables on an in-memory SQLite, `jsonb` resolving to `JSON` through the variant.
- [x] AC-08: The exclusion register is down to eight names, all one problem — seven tables with no model and one model whose table has a different name.

## 5) Testing Evidence (link to runs)
- [x] Lint — `black --check`, `isort --check-only`, `flake8` clean on every changed `src/`, `tests/` and `alembic/versions/` file. (`alembic/env.py` still reports the same one `isort` complaint and one `E402` it reported before this PR; unchanged and not this PR's.)
- [x] Typecheck — `mypy src`: **no issues found in 526 source files**. This is the check that mattered for the 25 nullability changes: every one of them widened a `Mapped[X]` to `Mapped[Optional[X]]`, and no call site needed a guard added because the read paths already had them.
- [x] Build — N/A
- [x] Unit tests — **5044 passed, 8 skipped, 0 failed** (`tests/unit`), the same count as #1530. One test needed editing and was corrected rather than weakened: `test_excluded_tables_are_read_from_alembic_env` asserts a *mid-set* name to prove the frozenset parser did not stop early; `information_assets` held that role and is no longer in the set, so it now asserts `risk_audit_mapping`. The assertion is the same strength — the comment above it already records `obsolete_document_records` having held the role before.
- [x] Integration tests — PostgreSQL 16.14. `alembic upgrade head` from empty, `downgrade -1`, re-upgrade, and upgrade over an already-converged schema (the adopt path: 0 widened, 0 foreign keys created) all clean. `tests/integration/test_all_endpoints.py` 69 passed; `test_declared_but_unmigrated_tables.py` and `test_run026_attribution_schema_parity.py` 10 passed, 6 skipped (all six skip on an empty `DECLARED_BUT_UNMIGRATED`, which 20260907 emptied).
- [ ] Contract tests (if applicable) — N/A, no API surface changed
- [ ] E2E Smoke (critical journeys) — not run. The ISO 27001 endpoints are covered by the integration run above.

Measured on PostgreSQL 16.14 against a database built by `alembic upgrade head`:

| | main (#1530 tip) | this PR |
| --- | --- | --- |
| `before_filter` operations / tables | 1058 / 209 | 1058 / 209 |
| unfiltered census (exclusions included) | 1225 / 226 | 1081 / 217 |
| drift hidden by `include_object` | 167 / 17 tables | **23 / 8 tables** |
| `AddColumnOp` anywhere | 0 | 0 |
| `DropColumnOp` hidden on excluded tables | 50 | **0** |
| census `database_only_columns_total` | 86 | **36** |
| exclusion register size | 17 | **8** |
| ratchet exit code | 0 | 0 |

`before_filter` being *unchanged* is the point: the nine tables joined the comparison and contributed nothing between them, the result `20260906_doc_ctl_children`, `20260907_ims_unification` and `20260908_soa_align` each produced.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `alembic upgrade head` on an empty PostgreSQL 16 database completes and reports 16 widened columns, 7 foreign keys and the comment
- [x] CUJ-02: `alembic check` under `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` reports "No new upgrade operations detected" with all nine names gone from the frozenset
- [x] CUJ-03: `scripts/validate_alembic_drift_ratchet.py --database-url ...` exits 0, reports 8 excluded tables carrying 23 operations, 0 `AddColumnOp`, and `exclusions with no drift left (removable): []`
- [x] CUJ-04: `scripts/ops/run026/audit_attribution_schema.py` reports 0 absent columns, 0 deferred, 0 failures and 36 database-only columns (was 86)
- [x] CUJ-05: create + list through the ORM on `access_control_records`, `business_continuity_plans`, `security_incidents`, `supplier_security_assessments` and `information_assets`, including a `jsonb` round-trip through the variant column

## 7) Observability & Ops
- **Logs:** The migration logs which columns it widened, which foreign keys it created and that the comment was set, at `alembic.runtime.migration`. A skipped table logs a line naming it.
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** `docs/governance/alembic_check_excluded_tables.md` (dated 2026-09-09 section; the "plural ORM names" category is retired) and `docs/governance/attribution_schema_drift.md` (the database-only column census falls from 95 to 36, and the nullability bullet records which way that class was settled and why)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** `alembic upgrade head`, then `scripts/ops/run026/audit_attribution_schema.py --json` and confirm `database_only_columns_total` is 36 and `failures` is 0. **Before deploying, run the orphan scan** the migration will run — a `SELECT count(*)` per column for rows naming a missing `users` row — so that a refusal is discovered before the deploy window rather than during it.
- **Canary plan:** N/A — no runtime surface changed
- **Prod post-deploy checks:** The same census, plus a spot read of one row from each of the seven ISO 27001 tables through the API. Note that production's physical schema was **not** reachable for this work: everything here is measured against a database built by this repository's own migration chain. The widenings are structural and expected to hold; the seven foreign keys are the step that depends on production data, and the migration is written to refuse rather than guess if it does not.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** `alembic upgrade head` refuses with `OrphanedReferenceError`, or the census reports something unexpected after deploy
- **Rollback steps:** On an `OrphanedReferenceError` nothing has been applied — PostgreSQL DDL is transactional and the migration raises before committing — so decide what those rows should point at and re-run. Otherwise `alembic downgrade 20260908_soa_align`, then revert the PR. If the downgrade refuses with `ValuesTooLongError`, some row holds a value longer than the original `varchar` limit, written since the widen; decide what that value should be rather than letting it be truncated.
- **Owner:** Platform / DBA, with IMS / ISO27001 for the six duplicated column pairs and for any decision to enforce the 25 nullability claims

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: To follow
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API or UX surface; the data decisions (database authoritative, drop nothing, keep both members of each duplicated pair, record rather than enforce nullability) are recorded in `docs/governance/alembic_check_excluded_tables.md`
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — census + orphan scan in §8
