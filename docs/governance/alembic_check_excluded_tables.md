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
| Legacy singular ISO27001 / ISMS names | Tables created by older migrations (e.g. `add_iso27001_isms`); ORM may use plural or different naming. |
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
| `access_control_record` | IMS / ISO27001 | Legacy singular table from ISO27001/ISMS migrations; excluded until singular↔plural rename or model alignment. |
| `business_continuity_plan` | IMS / ISO27001 | Legacy singular BCP table; ORM/plural alignment pending. |
| `information_asset` | IMS / ISO27001 | Legacy singular information-asset table; rename/model sync pending. |
| `information_security_risk` | IMS / ISO27001 | Legacy singular IS risk table; rename/model sync pending. |
| `iso27001_control` | IMS / ISO27001 | Legacy singular control table; rename/model sync pending. |
| `security_incident` | IMS / ISO27001 | Legacy singular security-incident table; rename/model sync pending. |
| `soa_control_entry` | IMS / ISO27001 | Legacy singular SoA entry table; rename/model sync pending. |
| `supplier_security_assessment` | IMS / ISO27001 | Legacy singular supplier assessment table; rename/model sync pending. |
| `access_control_records` | IMS / ISO27001 | Plural ORM name without matching migrated table (or rename pending). |
| `business_continuity_plans` | IMS / ISO27001 | Plural ORM name; migration/rename pending. |
| `controlled_document_versions` | Documents | Document-control ORM table not yet covered by migrations (or rename pending). |
| `controlled_documents` | Documents | Document-control ORM table not yet covered by migrations (or rename pending). |
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

## Maintenance

1. When adding a name to `_ALEMBIC_CHECK_EXCLUDED_TABLES`, add a row here in the same PR (owner + reason).
2. When removing a name, delete the row and cite the migration / model PR that made compare safe.
3. Prefer shrinking this list via migrations over widening CI op filters.

## Related

- Filter hook: `process_revision_directives` / `_filter_upgrade_ops` in `alembic/env.py`
- CI: `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` around `alembic check` in `.github/workflows/ci.yml`
