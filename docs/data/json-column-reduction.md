# JSON Column Reduction Plan (D11)

Tracking migration of JSON/JSONB columns to proper relational structures.

## Current JSON Columns

| Table | Column | Type | Contents | Migration Priority |
|-------|--------|------|----------|-------------------|
| `audit_findings` | `clause_ids_json_legacy` | JSON | Array of clause references | High |
| `audit_findings` | `control_ids_json` | JSON | Array of control IDs | High |
| `audit_findings` | `risk_ids_json` | JSON | Array of risk IDs | High |
| `risks_v2` | `linked_audits` | JSON | Array of audit references | Medium |
| `risks_v2` | `linked_actions` | JSON | Array of action references | Medium |
| `external_audit_import_jobs` | `score_breakdown_json` | JSONB | OCR score breakdown | Low (semi-structured) |
| `uvdb_audits` | `section_scores` | JSONB | Section-level scores | Low (semi-structured) |

## Migration Strategy

### Phase 1: Junction Tables for Finding Links

Replace `clause_ids_json_legacy`, `control_ids_json`, and `risk_ids_json` with proper junction tables:

- `audit_finding_clauses` (finding_id, clause_id)
- `audit_finding_controls` (finding_id, control_id)
- `audit_finding_risks` (finding_id, risk_id)

**Benefits**: Referential integrity, indexed lookups, proper foreign keys.

### Phase 2: Risk Links

Replace `linked_audits` and `linked_actions` on `risks_v2` with junction tables:

- `risk_audit_links` (risk_id, audit_reference)
- `risk_action_links` (risk_id, action_reference)

### Phase 3: Keep Semi-Structured as JSONB

`score_breakdown_json` and `section_scores` are genuinely semi-structured (variable keys/depths) and are appropriate for JSONB storage. No migration needed.

## Migration Approach

1. Create junction table via Alembic schema migration.
2. Create data migration to populate junction table from JSON column.
3. Update service layer to read/write junction table.
4. Update API schemas to use junction table data.
5. Deprecate JSON column (keep for backward compatibility during transition).
6. Drop JSON column in a subsequent migration after verification.

## Related Documents

- [`src/domain/models/audit.py`](../../src/domain/models/audit.py) — AuditFinding model
- [`src/domain/models/risk_register.py`](../../src/domain/models/risk_register.py) — EnterpriseRisk model
