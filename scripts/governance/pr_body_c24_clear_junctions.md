# Change Ledger (CL-001)

## 1) Summary

- **Feature / Change name:** C-24 final — drop six junction tables nothing reads, point `EscalationRule` at the table it describes, and empty the `alembic check` exclusion register (#1526)
- **User goal (1–2 lines):** Remove the last eight names from `_ALEMBIC_CHECK_EXCLUDED_TABLES`, so that no table anywhere in the repository is removed from `alembic check` by name and the published drift number is the whole of the deferral. Both remaining entries were dead weight holding a gate muted: six junction tables that no model, service or route has ever named, and one model that named a table which does not exist.
- **In scope:** `20260912_clear_junctions` (six `DROP TABLE`, one `ADD COLUMN` + index + foreign key, three `SET NOT NULL`); `EscalationRule.__tablename__` corrected to `escalation_rules_config` and `EscalationLog.rule_id` repointed at it; all eight names removed from `_ALEMBIC_CHECK_EXCLUDED_TABLES`, from `docs/governance/alembic_check_excluded_tables.md` and from `alembic_drift_baseline.json`; `docs/data/etl-service-permissions-fix.md` written for C-65 (diagnosis + two guarded statements, **neither applied**)
- **Out of scope:** Finishing the normalization `20260220_normalize_json` started — models for the six junctions, replacing the `_legacy` JSON reads in `risk.py` / `audit_service.py`, and the `clause_ids` / `control_ids` API contract change. That is `docs/data/json-column-reduction.md` and it is untouched. Also out: the operation-type filter (`ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1`), which is now the only mute left and is 1056 operations; `escalation_logs.tenant_id`'s absent foreign key, one of 102 of its class; row-level security on `escalation_rules_config`; the two stale `complaints` / `incidents` baseline rows; applying anything in the C-65 document
- **Feature flag / kill switch:** N/A — schema convergence
- **Stacks on:** nothing. Branches from `origin/main` at `1b05087a` (#1538).

## 2) Impact Map (what changed)

- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None. No handler or service was edited, and none could have been affected: **nothing in `src/`, `scripts/`, `frontend/src/` or `tests/` names any of the six junction tables, and nothing queries `EscalationRule`.** Verified by search. Every apparent hit on the junctions is the *plural* `risk_control_mappings`, which is a real model in `risk_register.py` and a different table; the two `EscalationRule` look-alikes are an unrelated `str` `Enum` in `workflow_service.py` and an `escalation_rules` JSON **column** on `workflow_definitions`.
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None. The `_legacy` JSON columns the application actually reads are untouched, so `clause_ids` / `control_ids` on the audit and risk payloads are unchanged.
- **Database (migrations/entities/indexes):** `alembic/versions/20260912_clear_junctions.py`. Drops `risk_clause_mapping`, `risk_control_mapping`, `risk_audit_mapping`, `risk_incident_mapping`, `audit_finding_clause_mapping`, `audit_section_clause_mapping`. On `escalation_rules_config`: adds `tenant_id` (nullable, `fk_escalation_rules_config_tenant_id` → `tenants.id`, `ix_escalation_rules_config_tenant_id`) and sets `trigger_unit`, `send_notification`, `is_active` `NOT NULL` after repairing any NULL to the column's own server default. **Drops no column and renames nothing.**
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Two problems, two different treatments, because neither is the column-shape disagreement the four preceding C-24 dates fixed by absorbing the database into the model.

  **The six junctions are a stale derived copy, not a second record.** `20260220_normalize_json` created them, copied five JSON array columns into them, and renamed the sources with a `_legacy` suffix. The second half of that plan never happened: no model was written, nothing reads them, and the application still reads the `_legacy` columns — `Risk.clause_ids_json_legacy` is mapped and read, `risk_clause_mapping` is not mapped at all. So every row in them was derived six months ago from a column that is still present, still authoritative, and has been written to ever since. `audit_section_clause_mapping` never had a source column and has never held a row anywhere.

  **`escalation_rules` was a model naming a table that does not exist.** `20260220_workflow_persist` created `escalation_rules_config`; the model declared `escalation_rules`. Both names went on the register — one as a table with no model, one as a model with no table — which is one mismatch recorded twice. The model is the side that was wrong, and it was not merely differently named: `select(EscalationRule)` raised `UndefinedTable` on every migrated database since February (confirmed — `to_regclass('escalation_rules')` is NULL on a database at the previous head). Nothing raised, because nothing queries it.

  For the three nullability disagreements on that table the **database** moves, by the 2026-09-08 rule — *the side that moves is the side whose move cannot lose or reject data*. The server default (`'hours'`, `true`, `true`) already guarantees a value on every row inserted without one, so the only row `SET NOT NULL` could reject is one where a NULL was written explicitly, and nothing has ever written to this table. Any such row is repaired to that same server default first and the count logged, so the outcome does not vary with what the table holds. Making the model `Optional` instead would ship a nullable boolean flag on a table that is about to get its first reader.

- **Tolerant reader / strict writer applied?** Yes, in the sense that matters here: nothing is inferred. The junction rows are not merged back into the `_legacy` columns and the `_legacy` columns are not re-derived from the junction rows — the two disagree after six months of divergence, and picking a winner is the normalization decision this PR explicitly does not make. The rows are dropped because their source is still there, and the upgrade **prints the row count of each table before dropping it**, so the deploy log is the record of what each environment discarded rather than this paragraph.
- **Breaking changes:** None at runtime. Three behavioural notes. (1) `EscalationRule` becomes queryable for the first time; a `select()` that used to raise now returns rows. There is no caller to change. (2) `escalation_logs.rule_id` now declares the foreign key the physical constraint has always had, so `EscalationLog.rule` style navigation would resolve — again, no caller. (3) An `INSERT` into `escalation_rules_config` that explicitly passes `NULL` for `trigger_unit`, `send_notification` or `is_active` would now be rejected instead of stored. Nothing does that; the ORM omits the columns and lets its Python default supply the value.
- **Migration plan:** `alembic upgrade head`. Every step is conditional on the current state, not on this migration having produced it: a table that is already absent is logged and skipped, `tenant_id` is adopted if already present, the index is created only if absent, and a column that is already `NOT NULL` is left alone. Verified against a partially-converged schema (see AC-07). The nullability step is **unconditional convergence**, not the data-conditional idiom `tests/unit/test_migration_schema_drift_lint.py` exists to catch: it repairs then tightens, so there is no outcome that depends on row data and nothing to fail on.
- **Rollback strategy (DB):** `alembic downgrade -1` relaxes the three columns, drops `tenant_id` and its index, recreates all six junction tables in their original shape, and **re-derives their rows from the same `_legacy` columns using the same SQL `20260220_normalize_json` used**. That is what makes the drop reversible rather than merely undoable — the source of every dropped row is still in the database. Verified byte-for-byte and with data (AC-05, AC-06).

## 4) Acceptance Criteria (AC)

- [x] AC-01: The exclusion register is **empty**. `_ALEMBIC_CHECK_EXCLUDED_TABLES` holds no names, `docs/governance/alembic_check_excluded_tables.md` has no inventory rows, and `alembic_drift_baseline.json` has `excluded_tables: []` and `excluded_table_drift: {}`. `alembic check` reports `0 table(s) are removed from the comparison entirely by include_object`.
- [x] AC-02: All eight names produce **zero** autogenerate operations. Measured on an unfiltered comparison with `include_object` allowing everything: 25 before (six junctions at `DropTableOp` 1 + `DropIndexOp` 2 each; `escalation_rules` at `CreateTableOp` 1 + `CreateIndexOp` 2; `escalation_rules_config` at `DropTableOp` 1 + `DropIndexOp` 1; and 2 on `escalation_logs` that the rename collapses), **0** after. `escalation_rules_config` joins the comparison contributing nothing.
- [x] AC-03: `AddColumnOp` stays at **0** across the whole repository. This mattered here rather than being a formality: the rename would otherwise have created the repository's only `AddColumnOp` — the class the ratchet fails on unconditionally — at the exact moment it made the class reachable, leaving `select(EscalationRule)` raising `UndefinedColumn` instead of `UndefinedTable`.
- [x] AC-04: No column is dropped and no table the application declares is removed. The migration contains no `op.drop_column` and no rename. After it, the only table in the migrated database that no model declares is **`alembic_version`**, and no declared table is absent — measured: `in db, not declared: ['alembic_version']`, `declared, not in db: []`. On `origin/main` the same measurement returns 8 undeclared and 1 absent.
- [x] AC-05: `downgrade` restores the six junction tables **byte-for-byte**. `pg_dump --schema-only` of the six tables plus `escalation_rules_config` after `upgrade head` → `downgrade -1` is identical to the same dump from a separately built database at `20260911_shared_severity`; the only diff is pg_dump's own random `\restrict` token.
- [x] AC-06: `downgrade` re-derives the dropped rows. Seeded a risk with `clause_ids_json_legacy = [901, 902]` and two matching junction rows; `upgrade` logged `dropping risk_clause_mapping (2 row(s))`, `downgrade` logged `recreated risk_clause_mapping with 2 re-derived row(s)`, and the two rows came back with the same `risk_id` / `clause_id` pairs.
- [x] AC-07: The migration is idempotent against a partially-converged schema. Ran it over a database where `tenant_id` had already been added (with an auto-named foreign key, not this migration's named one) and `is_active` was already `NOT NULL`: it logged `tenant_id already present, adopted unverified`, skipped `is_active`, tightened the other two, created the index — and the table still compares to **zero** operations, so the auto-named foreign key matches structurally.
- [x] AC-08: `EscalationRule` is readable and writable. `select(EscalationRule)` succeeds (it raises `UndefinedTable` on `origin/main`); an ORM insert lands with `tenant_id=1` and the three Python defaults filling the now-`NOT NULL` columns (`trigger_unit='hours'`, `send_notification=True`, `is_active=True`); and `EscalationLog.rule_id` resolves to the physical constraint, which `pg_constraint` confirms references `escalation_rules_config`.
- [x] AC-09: No other table's drift grew. `before_filter` falls from 1058 to 1056 across the same 209 tables, and the fully unfiltered census falls from **1081 across 217 to 1056 across 209** — exactly the 25 operations and 8 tables removed here. The 2-operation fall is on `escalation_logs`, whose `rule_id` foreign key was being reported as one `CreateForeignKeyOp` (the model's, against a table that did not exist) plus one `DropConstraintOp` (the database's, against a table with no model).
- [x] AC-10: `docs/data/etl-service-permissions-fix.md` exists, records the C-65 defect with its measured runtime effect, and **applies nothing**. Every statement is a labelled step with a guarded `WHERE`, the document is headed `BLOCKED`, and it states why the repair needs an owner rather than choosing for one: the two candidate repairs differ by two permissions that have never worked, one of which is `incident:set_reference_number`.

## 5) Testing Evidence (link to runs)

- [x] Lint — `black --check`, `isort --check-only`, `flake8` clean on `alembic/versions/20260912_clear_junctions.py`, `alembic/env.py`, `src/domain/models/workflow.py` and `tests/unit/test_tenant_scope_inventory_scripts.py`. `markdownlint-cli2` clean on the new `docs/data/etl-service-permissions-fix.md`; the pre-existing MD060 / MD012 / MD018 hits in `alembic_check_excluded_tables.md`, `absent-table-disclosure.md` and `schema-erd.md` are unchanged in count (36 MD060 on `absent-table-disclosure.md` before and after).
- [x] Typecheck — `mypy src`: **no issues found in 527 source files**.
- [x] Build — N/A
- [x] Unit tests — **5115 passed, 8 skipped, 0 failed** (`tests/unit`). One test needed editing, and it was **strengthened rather than weakened**: `test_excluded_tables_are_read_from_alembic_env` proved the frozenset parser had not stopped early by asserting a first, middle and last name were present, and with the register empty there is no name to assert. It is replaced by two tests — `test_the_exclusion_register_is_empty`, which pins the register itself, and `test_the_excluded_tables_parser_reads_a_populated_register`, which points the parser at a synthetic `env.py` carrying three names and a comment between them. That tests the same property more directly and keeps testing it however long the register stays empty.
- [x] Integration tests — PostgreSQL 16.14. `alembic upgrade head` from empty, `downgrade -1`, re-upgrade, upgrade over a partially-converged schema, and upgrade with seeded junction rows: all clean. `tests/integration/test_all_endpoints.py` **69 passed**. `test_declared_but_unmigrated_tables.py` + `test_run026_attribution_schema_parity.py` **10 passed, 6 skipped** (all six skip on an empty `DECLARED_BUT_UNMIGRATED`, which `20260907_ims_unification` emptied) — the same result the preceding C-24 PRs recorded.
- [ ] Contract tests (if applicable) — N/A, no API surface changed
- [ ] E2E Smoke (critical journeys) — not run. There is no user-facing surface over any of these eight tables; the endpoint smoke above is the coverage.

Measured on PostgreSQL 16.14 against a database built by `alembic upgrade head` from empty:

| | `origin/main` (`1b05087a`) | this PR |
| --- | --- | --- |
| `before_filter` operations / tables | 1058 / 209 | 1056 / 209 |
| unfiltered census (exclusions included) | 1081 / 217 | **1056 / 209** |
| drift hidden by `include_object` | 23 / 8 tables | **0 / 0 tables** |
| exclusion register size | 8 | **0** |
| `AddColumnOp` anywhere | 0 | 0 |
| tables in the database no model declares | 8 | **1** (`alembic_version`) |
| tables a model declares that are absent | 1 (`escalation_rules`) | **0** |
| `database_only_columns_total` (run026 census) | 36 | 36 |
| `audit_attribution_schema.py` failures | 0 | 0 |
| ratchet exit code | 0 | 0 |

Unlike the four preceding C-24 dates, `before_filter` does **not** stay the same, and that is worth being explicit about because "unchanged" has been the marker of a clean convergence throughout this work. It falls by 2, and both are on `escalation_logs` for the reason in AC-09 — a shrink, which the ratchet reports as a warning and which the baseline is tightened for in this PR.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: `alembic upgrade head` on an empty PostgreSQL 16 database completes, logs the row count and source column of each of the six dropped tables, and reports the three columns it tightened
- [x] CUJ-02: `alembic check` under `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` reports "No new upgrade operations detected" with the frozenset empty, and states `0 table(s) are removed from the comparison entirely by include_object`
- [x] CUJ-03: `scripts/validate_alembic_drift_ratchet.py --database-url ...` exits 0 and reports `drift hidden on those tables: 0 operation(s) across 0 table(s)`, 0 `AddColumnOp`, and `exclusions with no drift left (removable): []`. The only warnings are the two pre-existing `complaints` / `incidents` rows `origin/main` already warns on
- [x] CUJ-04: `scripts/ops/run026/audit_attribution_schema.py` reports 0 absent tables, 0 absent columns, 0 deferred, 0 failures, 36 database-only columns
- [x] CUJ-05: create, read and delete an `EscalationRule` through the ORM, including the three server-side/Python defaults and the `escalation_logs.rule_id` foreign key
- [x] CUJ-06: `downgrade -1` from head, then `upgrade head` again, on a database holding seeded junction rows — rows dropped with a logged count, re-derived on the way back, schema byte-identical

## 7) Observability & Ops

- **Logs:** The migration logs, at `alembic.runtime.migration`: one line per junction table naming its row count and the `_legacy` column that remains the source of record; a summary of how many were dropped and how many were already absent; one line per tightened column with the number of rows repaired and the value used; and a line if `tenant_id` was adopted rather than added. On `downgrade`, one line per recreated table with its re-derived row count, and a warning if a `_legacy` column is absent so the table comes back empty.
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** `docs/governance/alembic_check_excluded_tables.md` — dated 2026-09-12 section, both remaining categories retired, the inventory replaced by a statement of the shape a future inventory must take (because `validate_alembic_drift_ratchet.py` parses this file and a backticked snake_case name in a table's first column reads as an exclusion), and the suppression table extended with an "After 2026-09-12" column. `docs/ops/absent-table-disclosure.md` — dated note recording that `escalation_rules` is no longer an ORM name for anything. `docs/data/schema-erd.md` — the workflow child-table row corrected to `escalation_rules_config`. `docs/data/etl-service-permissions-fix.md` — new, for C-65.

## 8) Release Plan (Local → Staging → Canary → Prod)

- **Staging verification:** `alembic upgrade head`, then read the six `dropping <table> (N row(s))` log lines and record the counts — that is the only environment-specific fact this change has, and it is the number a reviewer would want if the decision is ever questioned. Then `alembic check` and the ratchet, and confirm the register reports 0 excluded tables.
- **Canary plan:** N/A — no runtime surface changed
- **Prod post-deploy checks:** The same three. **Before deploying, run the row counts read-only** so the numbers are known in advance rather than discovered in the deploy log: `SELECT 'risk_clause_mapping', count(*) FROM risk_clause_mapping UNION ALL ...` for all six. If any count is large, that is not a reason to stop — the rows are still derived from columns that are still there — but it should be recorded before rather than after. Note that production's physical schema was **not** reachable for this work: everything here is measured against a database built by this repository's own migration chain.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** `alembic upgrade head` fails, or a reader of one of the six junction tables is discovered after the fact
- **Rollback steps:** `alembic downgrade 20260911_shared_severity`, then revert the PR. The downgrade recreates all six tables and re-derives their rows from the `_legacy` columns, so a discovered reader finds the table populated from the same source it was populated from in February. PostgreSQL DDL is transactional, so a failed upgrade leaves nothing applied. If a reader is discovered, note that reverting restores a *stale* copy — the underlying question of which side of the half-finished normalization is authoritative is `docs/data/json-column-reduction.md`, not this PR.
- **Owner:** Platform / DBA, with Risk / Audit for any decision to finish the normalization the six junctions were the first half of, and — separately — a **named owner still needed for `etl-service`** before C-65 can proceed

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Staging deploy evidence: To follow
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no API or UX surface. The data decisions (the six junctions are a stale derived copy and are dropped rather than normalized; the model moves to the table's name, not the reverse; the database moves on the three nullability disagreements) are recorded in `docs/governance/alembic_check_excluded_tables.md` and in the migration's own docstring.
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — read-only row counts, `alembic check`, and the ratchet, in §8
