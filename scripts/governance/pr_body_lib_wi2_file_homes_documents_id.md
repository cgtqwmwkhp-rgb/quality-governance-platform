# PR body — Library WI-2: File homes → documents.id (L-32)

> **HOLD — do not open until WI-1 (#1687) is LIVE on main.**  
> This branch is prep-only: inventory + migrate dry-run + design + draft alembic.
> Opening now would either dual-head alembic against WI-1 or land docs without
> the schema owner.

## Summary

- L-32 / WI-2 prep: converge Planet Mark `carbon_evidence`, UVDB
  `documents_presented`, and optional `evidence_assets` Library links onto
  Register `documents.id` (F-7 migrate dispositions).
- Ships read-only inventory + migrate-prep scripts and unit tests that **do not**
  require a new alembic head.
- Draft alembic (``.py.draft``, not under `alembic/versions/`) revises WI-1 head
  `20261030_lib_wi1_cel` — activate only after WI-1 LIVE.

## Change Ledger

| Area | Change |
| --- | --- |
| Design | `docs/governance/library-file-homes-l32.md` |
| Prep scripts | `file_homes_inventory.py`, `file_homes_migrate_prep.py` |
| Tests | `tests/unit/test_lib_wi2_file_homes_prep.py` |
| Draft schema | `docs/governance/drafts/alembic_DRAFT_after_wi1_…py.draft` |
| Deferred | Live alembic + ORM `document_id` + promote routes |

## Compliance Delta

| Control | Impact |
| --- | --- |
| Document Register SoT (D1) | Prep toward single file home — no new blob table |
| F-3 anti-dupe | No allowlist growth; shrink deferred to later CUT |
| Alembic serial heads | Draft only; no competing revision while WI-1 open |

## Test plan

- [x] `PYTHONPATH=. python -m pytest tests/unit/test_lib_wi2_file_homes_prep.py -q`
- [x] `PYTHONPATH=. python -m scripts.governance.library.file_homes_inventory --json`
- [x] `PYTHONPATH=. python -m scripts.governance.library.file_homes_migrate_prep --demo`
- [ ] After WI-1 LIVE: copy draft → `alembic/versions/`, add ORM columns, dual-write promote paths, open implementing PR

## Out of scope / conflict hold

- WI-1 files (`compliance_evidence`, `standards.kind`, `clauses.catalogue_key`)
- DocumentDetail body
- `collaborative_*` drop (WJ-0)
- Live alembic under `alembic/versions/` while #1687 open
