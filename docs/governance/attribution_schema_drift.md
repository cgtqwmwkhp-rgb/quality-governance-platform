# Attribution columns and declared-but-absent columns (Run026)

Owner: Platform / DBA (schema truth), with the domain owners named below.

Two model-versus-database drifts were repaired in Run026, and several were
deliberately left alone. This records what was measured, how, what is verified
against a real database and what is not.

Tooling: `scripts/ops/run026/audit_attribution_schema.py` (read-only).
CI gate: the `alembic-check` job, after `alembic upgrade head`.

## Why the earlier numbers were low

Every census in this repository before Run026 enumerated the **model's** tables
and columns and asked the database about each one. For "the model declares a
column the database lacks" that direction is correct, and it is what
`verify_model_schema_parity` does. It still understated the count, for a
different reason: it skips every name in `_ALEMBIC_CHECK_EXCLUDED_TABLES`, so
absent columns on those ~40 tables were not deferred, they were invisible.

| Census | Absent columns found |
| --- | --- |
| `verify_model_schema_parity` (skips excluded tables) | 15 |
| `audit_attribution_schema` (skips nothing) | **19** |

For the attribution drift the model-driven direction is wrong outright. An
attribution column on a table with no model, or with an excluded model name,
cannot be seen by walking `Base.metadata` at all. `audit_attribution_schema`
enumerates that half from `information_schema` and `pg_constraint`.

The register at [`alembic_check_excluded_tables.md`](./alembic_check_excluded_tables.md)
is a maintained deferral list with named owners — it is not a silenced gate. What
went wrong is narrower and worth stating precisely: it defers **table-level**
compare noise, and it was being applied to **column-level** questions about
tables the database does have. The Run026 assertions do not filter by it.

## Drift 1: declared columns the database does not have

19 columns. Ranked by whether live code reads them, because that is what decides
urgency — not the column name.

A whole-entity ORM load emits **every** mapped column, so one absent column makes
the whole table unreadable, not just the queries that name the column. All nine
tables below were confirmed to raise `UndefinedColumn` on a plain
`SELECT <every mapped column>` executed against a migration-built PostgreSQL
database.

| Table | Absent | Live read path | Status |
| --- | --- | --- | --- |
| `capa_items` | `created_by_id`, `updated_by_id` | `GET /actions/`, `/actions/summary`, `/rca-tools/capa/*`, investigation closure gates | fixed |
| `legacy_key_risk_indicators` | `created_by_id`, `updated_by_id` | `GET /kri`, `/kri/dashboard`, `/executive-dashboard`, `/analytics/kpis`; `POST /kri` also **writes** `created_by_id` | fixed |
| `auditor_profiles` | `created_by_id`, `updated_by_id` | `GET /auditor-competence/profiles/{user_id}`, `/find-auditors/*`, `/dashboard` | fixed |
| `fishbone_diagrams` | `created_by_id`, `updated_by_id` | `GET`/`POST /rca-tools/fishbone/*` | fixed |
| `five_whys_analyses` | `created_by_id`, `updated_by_id` | `GET`/`POST /rca-tools/five-whys/*` | fixed |
| `workflow_rules` | `updated_by_id` | `GET`/`PATCH /workflow/rules/*`, escalation engine | fixed |
| `sla_configurations` | `created_by_id`, `updated_by_id` | `GET`/`PATCH /workflow/sla-configs/*` | fixed |
| `barrier_analyses` | `created_by_id`, `updated_by_id` | none — imported by `rca_tools` service but never queried | fixed anyway |
| `soa_control_entries` | `justification`, `implementation_method`, `risk_treatment_reference`, `tenant_id` | none — `SoAControlEntry` is never queried; the dead import in `iso27001.py` is not a read path | **deferred** |

Fixed by `alembic/versions/20260902_attribution_columns_add.py`.

### Why the model was right, for the 15

Worth arguing rather than assuming: dropping the columns from `AuditTrailMixin`
would also have made the schema self-consistent.

All eight tables carry `created_by VARCHAR(100)` and `updated_by VARCHAR(100)`
that no model declares. That looks like a half-finished rename, and it is not —
the varchar holds a name, the integer holds a user id. `20260121_add_workflow_engine`
created `workflow_rules` with `created_by_id INTEGER REFERENCES users(id)` **and**
`created_by VARCHAR(100)` in the same `create_table`, so id-based attribution
beside the legacy string is the intended design. 23 models already declare
`ForeignKey("users.id")` on `created_by_id`, and 31 physical tables already had
the column.

`created_by_id` is **not** backfilled from `created_by`. Resolving a free-text
name against `users` is inference — names are not unique, are not required to
match an account, and the value may be a display name, a username or an email
depending on which code wrote it. #1398 settled the principle. The new columns
are NULL on every existing row and `created_by` is retained as the only
attribution those rows have.

### Why `soa_control_entries` is deferred, not fixed

Owner: **IMS / ISO27001**.

This is not a table missing four columns. The physical table is a rename of the
legacy singular `soa_control_entry` (its sequence, primary key and foreign keys
still carry the singular name) and it holds a different design:

| Model declares | Database has |
| --- | --- |
| `justification` | `inclusion_justification`, `exclusion_justification` |
| `implementation_method` | `implementation_description` |
| `risk_treatment_reference` | — |
| `tenant_id` | — |
| — | `responsible_party`, `target_completion_date`, `updated_at` |

Which of the two justifications the model's single `justification` means is an
IMS domain question, not a schema question, and guessing it would silently
mis-file compliance evidence. Nothing is breaking while the owner decides:
`SoAControlEntry` has no live read path. The deferral is registered in
`DEFERRED_ABSENT_COLUMNS` in `audit_attribution_schema.py`, so the census reports
it every run instead of hiding it, and the gate fails if anything is added to it
without a decision.

`soa_control_entries.tenant_id` is additionally a tenancy/RLS question and
belongs with the `tenant_id` programme, not here.

## Drift 2: attribution columns with no foreign key

54 columns across **30** tables had no foreign key to `users`, so `created_by_id`
could name a user id that had never existed. Nothing objected: `AuditTrailMixin`
declared two bare integers, the database had no constraint, and `alembic check`
strips `CreateForeignKeyOp` under `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1`.

```
assessment_runs               engineers                     locations
asset_types                   evidence_assets               loler_examinations
assets                        external_audit_import_drafts  policies
audit_challenge_sessions      external_audit_import_jobs    policy_versions
audit_findings                incident_actions              risk_controls
audit_runs                    incidents                     risks
audit_templates               induction_runs                road_traffic_collisions
complaint_actions             investigation_runs            rta_actions
complaints                    investigation_templates       safety_insight_runs
compliance_evidence_links     documents                     training_tickets
```

29 inherit the columns from `AuditTrailMixin`. `compliance_evidence_links`
declares `created_by_id` directly on its model, which is why a sweep of mixin
subclasses missed it — the census enumerates from `pg_constraint` instead.

Fixed by `alembic/versions/20260902_attribution_foreign_keys.py`, and at the
model level by attaching the reference to the mixin itself (`declared_attr`,
because a `ForeignKey` cannot be shared between 42 tables). Constraining only the
database would have left the models declaring an integer where the database has a
reference — real drift, kept silent by that same CI filter.

### Orphans

`ADD CONSTRAINT ... FOREIGN KEY` validates every existing row, so a single
orphaned `created_by_id` aborts the `ALTER` mid-deploy with a driver error naming
nothing useful. The migration therefore counts first and raises
`AttributionOrphanRowsError` naming every table, column and count, plus the
read-only script to run — the same shape as #1398.

It does **not** null orphans out and does **not** delete them. An orphaned
`created_by_id` is the last remaining trace of who acted on a governance record,
most likely a user hard-deleted rather than deactivated, and discarding it to let
a deploy proceed destroys evidence. Re-creating the user with its original id
preserves the attribution; nulling the column does not.

The row-level-security guard is stricter than #1398's, because the hazard is
two-sided. `users` is itself under `FORCE ROW LEVEL SECURITY`, so for a role that
does not bypass RLS the `NOT EXISTS (SELECT 1 FROM users ...)` subquery can match
no user at all and report *every* attributed row in the database as an orphan,
refusing a migration that would have succeeded. A child table under FORCE RLS
gives the opposite error. `ADD CONSTRAINT` ignores RLS either way, so the
migration refuses to run on such a role rather than act on a count that is wrong
in an unknown direction.

## Verified against a database, versus inferred

**Verified** — on PostgreSQL 14 built by this repository's own alembic chain
(`alembic upgrade head` on an empty database), read back through
`information_schema` and `pg_constraint`:

- the 19 absent columns, and that all nine tables fail a whole-entity `SELECT`;
- the 54 unconstrained attribution columns across 30 tables;
- the 95 columns the database has that no model declares (see below);
- both migrations applying, downgrading and re-applying cleanly;
- the census reporting zero failures afterwards, and exit code 1 before;
- `alembic check` still green;
- 4100 unit tests and 810 PostgreSQL integration tests, matching `origin/main`.

**Not verified** — production and staging were unreachable:

- whether production holds **orphaned attribution values**. The migration-built
  database reports zero, which proves the constraint is addable to a clean schema
  and nothing about production. **Run the census against staging and production
  before deploying**, and expect the migration to refuse if either holds one.
- whether production's physical schema matches what the chain produces. Migrations
  in this chain are data-conditional in places (the WCS-TEN2 wave), so a database
  that held rows when they ran can differ from one that did not. The absent-column
  findings are structural `ADD COLUMN` gaps rather than conditional ones, so they
  are expected to hold, but that is an inference.
- `actionlint` on the CI change was not run locally.

```
env -u DATABASE_URL -u PRODDB -u STAGING_DB \
  DATABASE_URL=<dsn> \
  python -m scripts.ops.run026.audit_attribution_schema --json
```

## The direction no model-driven census can see

95 columns exist in the database that no model declares. Reported by the census,
ungated, because it is the direction every model-driven tool here is structurally
blind to — and on this repository it is what *explained* drift 1. The largest
groups:

| Table | Undeclared columns |
| --- | --- |
| `business_continuity_plans` | 15 |
| `supplier_security_assessments` | 12 |
| `iso27001_controls` | 10 |
| `security_incidents` | 7 |
| `access_control_records`, `soa_control_entries` | 6 each |
| `complaints`, `incidents`, `statement_of_applicability` | 4 each |
| `risks`, `users` | 3 each |
| the 8 tables in drift 1 | `created_by`, `updated_by` |
| `audit_questions`, `audit_responses`, `audit_sections` | `tenant_id` |

Out of scope for Run026 and not fixed. The IMS/ISO27001 group is the same
model-versus-migrated-design mismatch as `soa_control_entries` and belongs to
that owner. The `audit_*.tenant_id` group is the blind spot already documented in
`tests/integration/_run025_prodsim.py`.

## Deliberately left alone

- **~384 nullability mismatches** where a model says `nullable=False` and the
  column permits NULL. Deferred by decision. `verify_model_schema_parity` reports
  them; the Run026 census does not gate on them.
- **16 declared tables with no physical table**, all already in the exclusion
  register with owners (document-control children, IMS/ISO27001, `escalation_rules`,
  `unified_audit_plans`, and `root_cause_analyses` whose table a migration dropped).
- **`created_by` / `updated_by` varchar columns** on the eight tables. Retained,
  not dropped: they hold the only attribution those rows have.
- **Two pre-existing model-registry defects** found while building the test
  isolation, both present on `main` and neither touched:
  - `rta_analysis.RootCauseAnalysis` declares a relationship against
    `Incident.rtas`; `Incident` has no such property.
  - Two different classes named `Role` register on the same declarative base, so
    any relationship naming `"Role"` is ambiguous.

  Either one leaves `Base.registry` unable to configure once the module is
  imported, which then breaks any later code that instantiates any mapped class.
  This is why `tests/_run026_model_probe.py` does its importing in a subprocess.
