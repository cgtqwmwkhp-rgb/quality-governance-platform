# Risk assessments `tenant_id` backfill (WCS-TEN2)

Fail-safe NOT NULL on child table `risk_assessments.tenant_id` without inventing `tenant_id=1`.

## Inheritance

Backfill from parent `risks` via the NOT NULL FK `risk_assessments.risk_id`.
Rows whose parent `risks.tenant_id` is still NULL stay NULL until the parent is attributed.

## Operator steps

1. Backfill NULL assessments from the parent risk when `risks.tenant_id IS NOT NULL`.
2. Align mismatches so the child matches the parent when the parent is attributed
   (`IS DISTINCT FROM` + parent non-NULL).
3. Count remaining NULL `risk_assessments.tenant_id`.
4. **Fail-safe:** if count is 0 → `ALTER … SET NOT NULL`. If count > 0 → log a
   warning and leave nullable.

Create paths stamp `tenant_id` from the parent risk (never invent a default).

## Verification

```sql
SELECT count(*) AS null_parent_blocks
FROM risk_assessments AS a
LEFT JOIN risks AS r ON r.id = a.risk_id
WHERE a.tenant_id IS NULL;

SELECT count(*) AS attributable
FROM risk_assessments AS a
JOIN risks AS r ON r.id = a.risk_id
WHERE a.tenant_id IS NULL
  AND r.tenant_id IS NOT NULL;
```
