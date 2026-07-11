# risks_v2 `tenant_id` backfill (WCS-TEN2)

Fail-safe NOT NULL on parent core `risks_v2.tenant_id` without inventing `tenant_id=1`.

## Inheritance

Backfill from `users` via `created_by`, then `risk_owner_id`. Never invent a default tenant.

## Fail-safe

Only `ALTER … SET NOT NULL` when residual NULL count is 0.
