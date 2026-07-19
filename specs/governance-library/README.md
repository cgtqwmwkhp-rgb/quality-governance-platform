# Governance Document Library — spec pack (adapted for QGP)

This folder holds the taxonomy seed source used by Governance Library Wave W0
(`feat/gov-lib-w0-taxonomy-pel`). The original spec pack (`SPEC.md`,
`access-policy.md`, `types.ts`) was written for a from-scratch Azure/Cosmos DB
build and is **not** implemented as-is — it is reconciled with the existing
Quality Governance Platform (QGP) data model per the locked decisions below.
Only the taxonomy seed data (`taxonomy.json`) and its validator
(`seed/validate.mjs`) are carried over unmodified; everything else is
reinterpreted onto QGP's SQLAlchemy/Alembic/FastAPI stack.

## Locked decisions (Wave W0)

- **Library Document = file SoT; `ControlledDocument` = control layer.**
  QGP's existing `documents` table (`src/domain/models/document.py`) is the
  file system-of-record. The taxonomy/PEL reference scheme attaches to
  `documents`, not to `controlled_documents`.
- **`PEL-XXX-NN-###` sits alongside the existing `DOC-YYYY-####` reference.**
  `documents.reference_number` (DOC-YYYY-####, via `ReferenceNumberService`)
  is untouched. `documents.pel_doc_ref` is a new, separate, nullable+unique
  column allocated atomically per level-2 category.
- **Taxonomy category `06.04` (O-Licence & Tachograph — HGV) is seeded
  `active=false`.** Plantexpand does not currently run HGVs under an
  operator's licence; the category stays in the taxonomy (for provenance /
  future activation) but is excluded from active-category listings and
  cannot be assigned to new documents.
- **`iso-9001` / `iso-14001` / `45001` / `27001` are dropped from the
  required tag seed.** `planet-mark` and the taxonomy's subject-area tags are
  kept. Standards mapping remains handled by QGP's existing Standards
  Library module — this taxonomy's tag vocabulary is document-classification
  only, not certification scope.
- **Sites = existing `Location` model.** The spec pack's `sites` collection
  is not a new table; documents promote/bind to QGP's `locations` table
  (`src/domain/models/location.py`), already CRUD-able by admins under
  `/api/v1/assets/locations`.

## Out of scope for W0 (tracked as follow-ups)

- Review packs / AI horizon scan (SPEC.md §7.3) — thin backend landed in Wave W3
  (`/api/v1/library-review`, stub horizon provider); FE + live providers deferred.
- Disposal queue (SPEC.md §8) — not implemented; retention rules are
  carried as informational text on `document_categories.retention_rule`
  only, not automated.
- Full Entra ID / Azure Blob rebuild — QGP already has its own auth and
  storage layers; this wave reuses them instead of the spec pack's platform
  assumptions.

## Files

| File | Purpose |
|---|---|
| `taxonomy.json` | Unmodified seed source — 13 sections + 73 subcategories = 86 categories, with `ref_prefix`, `default_access`, `review_cycle`, `retention_rule`. Loaded by `scripts/governance/library/seed_document_categories.py`. |
| `seed/validate.mjs` | Unmodified sanity-check script — run `node specs/governance-library/seed/validate.mjs` before re-seeding after any taxonomy edit. |

See `docs/governance/decision-log-template.md` conventions and
`scripts/governance/pr_body_gov_lib_w0_taxonomy_pel.md` for the full Change
Ledger for this wave.
