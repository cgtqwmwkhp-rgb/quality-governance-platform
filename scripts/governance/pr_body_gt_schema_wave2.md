# Change Ledger (CL-GT-SCHEMA-WAVE2)

## File allowlist (exclusive)

- `alembic/versions/20260720_ea_tenant_nn.py`
- `alembic/versions/20260720_capa_src_chk.py`
- `alembic/versions/20260720_gt_src_sync.py`
- `src/domain/models/capa.py`
- `src/domain/models/evidence_asset.py`
- `src/domain/services/capa_service.py`
- `src/domain/services/evidence_service.py`
- `src/domain/services/investigation_service.py`
- `docs/data/evidence-assets-tenant-backfill.md`
- `docs/data/investigation-templates-tenant-waiver.md`
- `tests/unit/test_capa_source_integrity.py`
- `tests/unit/test_capa_golden_thread_source_check.py`
- `tests/unit/test_evidence_assets_tenant_not_null.py`
- `tests/unit/test_evidence_source_integrity.py`
- `scripts/governance/pr_body_gt_schema_wave2.md`

**Zero overlap** with OpenAPI baseline regen (D22), Azure DI enablement, or SWA YAML.

## 1) Summary

- **Feature / Change name:** fix(gt) — schema FK/NOT NULL residuals wave 2 (R47/R48/R62/R63; R77/R78 waived)
- **User goal:** Clear golden-thread UAT schema flags with fail-safe migrations + CHECK integrity (no unsafe polymorphic FKs)
- **In scope:** evidence tenant backfill+NOT NULL; CAPA GT source CHECK; evidence source_id CHECK + orphan report; finding↔risk junction sync; app stamp/validate; waivers for template NOT NULL + assigned_entity FK
- **Out of scope:** Dropping risk_ids_json / linked_risk_ids CSV; hard polymorphic FKs; OpenAPI regen
- **Root cause:** Wave-1 left soft links and conditional NOT NULL residuals after junction/RLS MVP

## 2) Impact Map

| Flag | Before | After |
|------|--------|-------|
| R62 | Partial parent backfill; ORM nullable | Expanded backfill + creator path; fail-safe NOT NULL; upload stamps tenant_id |
| R47 | audit_finding-only CHECK | GT CHECK (incident/nm/rta/investigation/audit_finding) + validate on create |
| R63 | Soft polymorphic source | source_id presence CHECK + orphan report; expanded validate_source_exists |
| R48 | Dual-write residual drift | Idempotent junction sync from risk_ids_json |
| R77 | Default template missing tenant | App stamps tenant_id; DB NOT NULL **WAIVED** (catalog) |
| R78 | No assigned_entity FK | **WAIVED** — app validate_assigned_entity + unique source index |

## 3) Compatibility & Data Safety

- Migrations: `20260720_ea_tenant_nn` → `20260720_capa_src_chk` → `20260720_gt_src_sync` (≤32 char ids)
- Never invent tenant_id=1; NOT NULL only at zero nulls
- CHECK replace is reversible; junction sync additive
- Rollback: downgrade gt_src_sync → capa_src_chk → ea_tenant_nn

## 4) Acceptance Criteria

- [x] AC-01: evidence backfill expands parents + creator; fail-safe NOT NULL
- [x] AC-02: CAPA GT sources require source_id (model + migration CHECK)
- [x] AC-03: evidence source_id presence CHECK + orphan report (no hard FK)
- [x] AC-04: audit_finding_risks re-synced from risk_ids_json
- [x] AC-05: EvidenceService stamps tenant_id; CAPA create validates sources
- [x] AC-06: Default investigation template stamps tenant_id; R77/R78 waived with docs
- [ ] AC-07: tip==LIVE; canvas flags flipped/waived with prod evidence

## 5) Testing Evidence

- Unit: capa GT check, evidence tenant nn, evidence source integrity, capa source integrity update
- [ ] CI green post-push

## 6) Critical Journeys

- [x] CUJ-01: CAPA from near_miss/incident requires source_id
- [x] CUJ-02: Evidence upload stamps tenant_id
- [x] CUJ-03: Finding↔risk junction absorbs JSON drift

## 7) Observability

- Migration WARNING logs for FAIL-SAFE nulls and orphan counts

## 8) Release Plan

- After D22 tip==LIVE → squash-merge → migrate three revisions → canvas re-score

## 9) Rollback Plan

- Revert squash; downgrade three revisions when safe

## 10) Evidence Pack

- Canvas GT UAT flags R47/R48/R62/R63/R77/R78
- Prior tip: D22 OpenAPI / `a0f2da85`

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [ ] **Gate 1:** Lint/type — touched surfaces
- [ ] **Gate 2:** Unit suites green
- [ ] **Gate 3:** Staging verification (auto after merge)
- [x] **Gate 4:** Canary N/A (schema integrity; no FE bake required)
- [ ] **Gate 5:** tip==LIVE + canvas update
