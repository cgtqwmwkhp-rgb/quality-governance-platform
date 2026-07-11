# Road traffic collisions `tenant_id` backfill (WCS-TEN2)

## Goal
Fail-safe NOT NULL on parent core `road_traffic_collisions.tenant_id` without inventing `tenant_id=1`.

## Attribution order
1. Copy from `users.tenant_id` via `road_traffic_collisions.created_by_id` when the creator is attributed.
2. Secondary: copy from `users.tenant_id` via `road_traffic_collisions.reporter_id` for residual NULLs.
3. Align mismatches to creator tenant when creator is attributed.

## Fail-safe
If any row remains `tenant_id IS NULL` after backfill, the migration **leaves the column nullable**, logs a warning, and succeeds.

## Create path
`create_rta` stamps `tenant_id` and `created_by_id` from the caller.
