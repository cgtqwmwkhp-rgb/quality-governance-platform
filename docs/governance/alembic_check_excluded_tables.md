# Alembic check excluded tables

Owner: Platform / DBA (schema truth) with domain owners below.

This document inventories every table name in `_ALEMBIC_CHECK_EXCLUDED_TABLES`
in [`alembic/env.py`](../../alembic/env.py). Those names are omitted from
`alembic check` / autogenerate compare via `include_object` until additive
migrations (or model alignment) land.

**Do not remove an exclusion without a migration or model fix that makes
`alembic check` green without the name in the frozenset.**

## Why exclusions exist

| Category | Reason |
| --- | --- |
| Plural ORM names | SQLAlchemy models declare plural `__tablename__` values that are not yet migrated (or rename is pending). |
| Junction / config without models | Tables exist in PostgreSQL but have no (or incomplete) SQLAlchemy models, so compare would invent drop/create noise. |
| ORM vs migrated name mismatch | Model table name differs from the live migrated table (e.g. `escalation_rules` vs `escalation_rules_config`). |
| Retained model after drop | Model still imported for metadata while the physical table was dropped by a later migration. |

CI sets `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` so `process_revision_directives`
can strip noisy FK / index / unique / column ops. Phase 2 trialled surfacing unique
`DropConstraintOp` drift, but CI found 19 unique-constraint removals; suppression remains
until model/migration alignment lands. `AddColumnOp` / `AlterColumnOp` remain deferred
because ORM vs migrated column shapes still differ widely. CI now publishes the
`alembic-drift-inventory` artifact, which lists autogenerate operations before and after
filtering for every check attempt and is the safe incremental Phase 2 step.

## Inventory

| Table name | Owner | Reason |
| --- | --- | --- |
| `access_control_records` | IMS / ISO27001 | Plural ORM name without matching migrated table (or rename pending). |
| `business_continuity_plans` | IMS / ISO27001 | Plural ORM name; migration/rename pending. |
| `cross_standard_mappings` | IMS / ISO27001 | Cross-standard mapping ORM table; migration coverage pending. |
| `document_access_logs` | Documents | Document access-log ORM table; migration coverage pending. |
| `document_approval_actions` | Documents | Approval-action ORM table; migration coverage pending. |
| `document_approval_instances` | Documents | Approval-instance ORM table; migration coverage pending. |
| `document_approval_workflows` | Documents | Approval-workflow ORM table; migration coverage pending. |
| `document_distributions` | Documents | Distribution ORM table; migration coverage pending. |
| `document_training_links` | Documents | Training-link ORM table; migration coverage pending. |
| `ims_control_requirement_mappings` | IMS / ISO27001 | IMS control↔requirement mapping ORM; migration coverage pending. |
| `ims_controls` | IMS / ISO27001 | IMS controls ORM; migration coverage pending. |
| `ims_objectives` | IMS / ISO27001 | IMS objectives ORM; migration coverage pending. |
| `ims_process_maps` | IMS / ISO27001 | IMS process-map ORM; migration coverage pending. |
| `ims_requirements` | IMS / ISO27001 | IMS requirements ORM; migration coverage pending. |
| `information_assets` | IMS / ISO27001 | Plural ORM counterpart to legacy singular; alignment pending. |
| `information_security_risks` | IMS / ISO27001 | Plural ORM counterpart to legacy singular; alignment pending. |
| `iso27001_controls` | IMS / ISO27001 | Plural ORM counterpart to legacy singular; alignment pending. |
| `management_review_inputs` | IMS / ISO27001 | Management-review input ORM; migration coverage pending. |
| `management_reviews` | IMS / ISO27001 | Management-review ORM; migration coverage pending. |
| `obsolete_document_records` | Documents | Obsolete-document ORM; migration coverage pending. |
| `security_incidents` | IMS / ISO27001 | Plural ORM counterpart to legacy singular; alignment pending. |
| `soa_control_entries` | IMS / ISO27001 | Plural ORM counterpart to legacy singular; alignment pending. |
| `supplier_security_assessments` | IMS / ISO27001 | Plural ORM counterpart to legacy singular; alignment pending. |
| `unified_audit_plans` | Risk / Audit | Unified audit-plan ORM; migration coverage pending. |
| `audit_finding_clause_mapping` | Risk / Audit mappings | Junction table present in DB without a complete SQLAlchemy model surface for compare. |
| `audit_section_clause_mapping` | Risk / Audit mappings | Junction table present in DB without a complete SQLAlchemy model surface for compare. |
| `escalation_rules_config` | Platform / DBA | Config table in DB; ORM uses a different name (`escalation_rules`). |
| `risk_audit_mapping` | Risk / Audit mappings | Junction mapping in DB without matching ORM compare coverage. |
| `risk_clause_mapping` | Risk / Audit mappings | Junction mapping in DB without matching ORM compare coverage. |
| `risk_control_mapping` | Risk / Audit mappings | Junction mapping in DB without matching ORM compare coverage. |
| `risk_incident_mapping` | Risk / Audit mappings | Junction mapping in DB without matching ORM compare coverage. |
| `escalation_rules` | Platform / DBA | ORM table name differs from migrated `escalation_rules_config`. |
| `root_cause_analyses` | Risk / Audit | Model retained in metadata after migration dropped the physical table. |

## Scope of an exclusion: intended table-level, actually total

An entry here is *intended* to defer **table-level** autogenerate compare for that
name. It is not a statement that anything about the table is acceptable.

Mechanically, though, it is not table-level at all. `include_object` returning
`False` removes the table from the comparison before column comparison happens, so
`alembic check` cannot report a column a model declares that the physical table
lacks on any excluded table. Measured: `soa_control_entries` declares four columns
the migrated database does not have (`implementation_method`, `justification`,
`risk_treatment_reference`, `tenant_id`), and the published drift inventory
contains zero `AddColumnOp` — because the table is on this list, not because the
columns are there. `scripts/validate_alembic_drift_ratchet.py --database-url ...`
runs a second, unfiltered comparison specifically to put a number on that, and
`scripts/ops/run026/audit_attribution_schema.py` reports it per column.

Run026 found that distinction being lost. `scripts/ops/run025/verify_model_schema_parity.py`
filters its column comparison by this frozenset, so declared-but-absent columns on
these ~40 tables were not deferred, they were unreported — the difference between
15 findings and 19. Tools that ask column-level questions should not filter by this
list; `scripts/ops/run026/audit_attribution_schema.py` does not, and reports each
finding's exclusion status as a field instead of dropping it.

See [`attribution_schema_drift.md`](./attribution_schema_drift.md).

## How much is actually suppressed, and what stops it growing

Two separate mutes are in play, and only one of them is this list:

| Mute | Mechanism | Measured on main (2026-07-29) |
| --- | --- | --- |
| Operation-type filter | `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` strips seven op types in `_filter_upgrade_ops` | 1060 operations across 209 tables reduced to 0 |
| Table exclusion (this list) | `include_object` drops the table from the comparison entirely | 33 tables carrying 216 further operations, including 4 `AddColumnOp` |

The op-type filter, not this list, is what makes the gate green: the exclusion list
removes its tables from the comparison before any operation is generated for them,
so nothing of theirs ever reaches the filter or the published `before_filter`
count. Both numbers are now printed by `alembic check` itself and enforced by
`scripts/validate_alembic_drift_ratchet.py`, which fails CI when:

- any `AddColumnOp` appears on a non-excluded table (zero tolerance — the count is
  0, and one absent declared column makes a whole table unreadable to a
  whole-entity ORM load);
- a table acquires drift, or an operation type, or a higher count than
  `alembic_drift_baseline.json` records;
- an excluded table's drift grows above its baseline;
- a name is in `_ALEMBIC_CHECK_EXCLUDED_TABLES` with no row in this document, or a
  row here names a table that is not excluded.

Drift *shrinking* is reported as a warning, not a failure, so that landing a
migration is never punished with a red gate. Refresh the baseline in the same PR.

## Maintenance

1. When adding a name to `_ALEMBIC_CHECK_EXCLUDED_TABLES`, add a row here in the same PR (owner + reason). This is enforced by `scripts/validate_alembic_drift_ratchet.py`.
2. When removing a name, delete the row and cite the migration / model PR that made compare safe.
3. Prefer shrinking this list via migrations over widening CI op filters.
4. Do not filter a column-level check by this list. See the section above.
5. `alembic check` alone cannot tell you whether an entry is still needed, because an excluded table produces no operations by construction. Run `scripts/validate_alembic_drift_ratchet.py --database-url ...` against a migrated database; it lists the entries with no drift left.

## Related

- Filter hook: `process_revision_directives` / `_filter_upgrade_ops` in `alembic/env.py`
- CI: `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` around `alembic check` in `.github/workflows/ci.yml`


## 2026-07-11 create + unfilter

Added `20260711_ctl_docs_create` so fresh migrate materializes `controlled_documents`
and `controlled_document_versions` (previously only TEN2/RLS migrations assumed they
existed). Removed both names from `_ALEMBIC_CHECK_EXCLUDED_TABLES` so alembic check
covers them. Child document-control tables remain excluded until create coverage lands.

## 2026-07-29 eight stale entries removed

Removed the whole "Legacy singular ISO27001 / ISMS names" group:
`access_control_record`, `business_continuity_plan`, `information_asset`,
`information_security_risk`, `iso27001_control`, `security_incident`,
`soa_control_entry`, `supplier_security_assessment`.

No migration was needed, because there was nothing to defer. Each of these names is
in neither `Base.metadata` nor the migrated schema — the migrations that created the
singular tables were superseded by the plural ones, and a name that exists on
neither side of the comparison generates no operation whether it is excluded or not.
Measured by running `alembic.autogenerate.produce_migrations` against a database
built by `alembic upgrade head` with `include_object` allowing everything: all eight
produced zero operations of any type, on both PostgreSQL 14.20 and 16.14. `alembic
check` stays green with them gone, and `before_filter` is unchanged at 1060
operations.

The plural counterparts (`information_assets`, `security_incidents`,
`soa_control_entries`, `supplier_security_assessments`, `iso27001_controls`,
`access_control_records`, `business_continuity_plans`) do carry real drift and stay.

