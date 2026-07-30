# Action-ownership count reconciliation (w3-owner-count / PX-168)

**Status:** reconciled as a labeling hazard, not an open register bug.
**Closes board item:** `w3-owner-count` — *Reconcile action-ownership counts before declaring PX-168 fixed*.

## What disagreed

Two measurements shared a total of **21** actions but disagreed on ownership:

| Source | Claim |
| --- | --- |
| Direct database count | **8 of 21** actions have an owner |
| `GET /api/v1/actions/` | **0 of 21** actions have an owner |

Same denominator, different numerator — almost always two tables (or two column names) behind one label.

## Which number is which

The unified Actions register reads **six** physical tables. They do **not** share one ownership column:

| Table | Physical ownership column | Unified response field |
| --- | --- | --- |
| `incident_actions` | `owner_id` | `owner_id` |
| `rta_actions` | `owner_id` | `owner_id` |
| `complaint_actions` | `owner_id` | `owner_id` |
| `investigation_actions` | `owner_id` | `owner_id` |
| `capa_actions` | `assigned_to_id` | `owner_id` (mapped) |
| `capa_items` | `assigned_to_id` | `owner_id` (mapped) |

- **Register truth** ("how many Actions have an owner?") = sum of rows where each store's *real* ownership column is set. That matches `GET /api/v1/actions/` items with non-null `owner_id` after the CAPA mapping in `src/api/routes/actions.py` (`_capa_to_response` / `_capa_item_to_response`).
- **Naive `owner_id` SQL on CAPA tables** is a different question. `capa_actions` and `capa_items` have **no** `owner_id` column, so a query written against that name either fails or silently misses every CAPA assignee. That is sufficient to turn "8 owned" into "0 owned" while keeping the same total of 21.

PX-168 itself (create path discarding `owner_id`) is a separate defect and is covered by the write-contract / actions API tests. This note only settles the **count label**.

## How to re-measure

Machine-readable label map: `scripts/governance/action_ownership_denominators.py`.

Against any DSN the suite already uses:

```bash
python scripts/governance/reconcile_action_ownership_counts.py --tenant 1
```

Output columns:

- `total` — rows in that store (optionally tenant-filtered)
- `owned_correct(<real column>)` — the denominator to trust
- `owned_naive(owner_id)` — what a mislabeled probe would report (`n/a` when the column does not exist)

Executable specs:

- `tests/unit/test_action_ownership_count_spec.py` — column map + CAPA → `owner_id` mapping + naive-hazard lock
- `tests/integration/test_action_ownership_count_spec.py` — seeded CAPA (`assigned_to_id`) and incident action (`owner_id`) both appear owned on `GET /actions/`

## Product fix?

None in this change. The unified list already maps both columns onto `owner_id` and filters with the correct physical column per store (`_apply_owner_and_overdue_filters`). The defect was **reporting two different predicates under one "ownership" label**, not a bulk-link gap and not a second create-path bug.
