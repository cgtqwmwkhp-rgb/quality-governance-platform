# Evidence assets tenant_id backfill (R62)

**Migration:** `alembic/versions/20260720_ea_tenant_nn.py`  
**Prior:** `20260719_rls_gt_exp` (partial parent backfill + conditional NOT NULL)

## Attribution order

1. Polymorphic parent tables by `source_module` → `source_id`
   - incident, near_miss, road_traffic_collision, complaint, investigation
   - audit → `audit_runs`, asset → `assets`, certificate → `certificates`
   - assessment → `assessment_runs`, induction → `induction_runs`
2. Secondary: `created_by_id` → `users.tenant_id`
3. **Never** invent `tenant_id=1`

## Fail-safe

`SET NOT NULL` only when `COUNT(*) WHERE tenant_id IS NULL = 0`.
Otherwise leave nullable and log `FAIL-SAFE` warning.

## App writers

`EvidenceService.upload` stamps `tenant_id` on create.
