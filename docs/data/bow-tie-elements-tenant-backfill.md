# bow_tie_elements `tenant_id` backfill (WCS-TEN2)

Fail-safe NOT NULL on child table `bow_tie_elements.tenant_id` without inventing `tenant_id=1`.

## Inheritance

Backfill from parent `risks_v2` via the NOT NULL FK `bow_tie_elements.risk_id`.

## Fail-safe

Only `ALTER … SET NOT NULL` when residual NULL count is 0.
Create paths stamp `tenant_id` from the parent risk.
