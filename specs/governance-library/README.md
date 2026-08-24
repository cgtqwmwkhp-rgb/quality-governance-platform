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
  **Forward scheme (Accepted, ADR-0023):** new allocations become
  `PEL-<FUNCTION>-<SEQ>` (function axis, not category path). Category
  `ref_prefix` remains a filing default until the Function-axis wave
  revises counters. Do **not** cite ADR-0020 for this — ADR-0020 is the
  Compliance Schedule occurrence model.
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
- Disposal queue (SPEC.md §8) — Wave W5 adds an admin-only dry-run queue at
  `GET /api/v1/documents/admin/disposal`. It lists only inactive lifecycle
  documents with an explicit, elapsed `retention_until`, and carries each
  category's `retention_rule` as provenance. Hard disposal is separately
  gated by `LIBRARY_DISPOSAL_EXECUTE=false` by default.
- Full Entra ID / Azure Blob rebuild — QGP already has its own auth and
  storage layers; this wave reuses them instead of the spec pack's platform
  assumptions.

## Files

| File | Purpose |
|---|---|
| `taxonomy.json` | Unmodified seed source — 13 sections + 73 subcategories = 86 categories, with `ref_prefix`, `default_access`, `review_cycle`, `retention_rule`. Loaded by `scripts/governance/library/seed_document_categories.py`. Since WA-2, `ref_prefix` is a filing default only — it no longer determines the reference (see `functions.json`). |
| `functions.json` | WA-2 / ADR-0023 — the 11 owning-function codes seeded into `document_functions` (**includes OPS**). Northern Star v6 replaces OPS with CTR+SVC (12 codes) — reseed is conveyor wave **W2**, not this file until that PR. |
| `northern-star-v6.json` | **Northern Star authority pack** — PEL-HSEQ-5014 v6.0 FINAL payload (`schema_version` 3.2): 388 documents, relationships, rules, taxonomy, legislation. Do not treat as an auto-applied seed; Waves W3+ index/upload against it. |
| `northern-star-rules-v6.json` | Slim extract: levels, 12 functions, R01–R32, workflow transitions, review triggers — for engineers implementing validators without loading the full pack. |
| `steward_retention_decisions.json` | **STEWARD-14 / CIT-1** — the accepted steward reading of the fourteen `retention_rule` values the CUT-1 grammar refuses, as `taxonomy_id` → `retention_years` + `retention_anchor` + rationale. Holds **only** the decision: no prose is copied here and `taxonomy.json` `retention_rule` is unchanged and remains the R19 basis. Loaded by `src/domain/services/library_steward_retention.py`, applied by the seed and by `20261103_lib_steward14`, and gated in CI by `scripts/governance/library/citation_cutover_readiness.py --fail-on-blockers`. Editing this file changes what documents are disposable — see `docs/governance/library-cut1-retention-access-sor.md` §STEWARD-14 for the rules a new decision must satisfy. |
| `seed/validate.mjs` | Unmodified sanity-check script — run `node specs/governance-library/seed/validate.mjs` before re-seeding after any taxonomy edit. |

## Northern Star (locked 2026-08-09)

Dry-run ingest (Wave **W5b**): `python -m scripts.governance.library.northern_star_dry_run_ingest` — report only, never silent write.

Nightly honesty (Wave **W9** / NS-NIGHTLY): `python -m scripts.governance.library.northern_star_nightly_honesty` — R08 / R25 / R30 pack reports only; `--guard` refuses fabricated zeros against `docs/governance/library_ns_nightly_honesty_baseline.json`. Scheduled via `.github/workflows/ns-nightly-honesty.yml`.

Programme master plan: Cursor canvas `library-v6-northern-star-master-plan`.
ADR amendment: `docs/adr/ADR-0023-governance-library-reference-scheme.md`
§ Amendment — Northern Star.

See `docs/governance/decision-log-template.md` conventions and
`scripts/governance/pr_body_gov_lib_w0_taxonomy_pel.md` for the full Change
Ledger for this wave.

Related FIRST-pack design notes (enhance, do not twin):

- `docs/adr/ADR-0023-governance-library-reference-scheme.md` — function PEL scheme + Northern Star amendment
- `docs/governance/library-clause-identity-d14.md` — `ALL_CLAUSES` ↔ `clauses`
- `docs/governance/library-cel-harden-d15.md` — CEL harden; never coverage_claims
- `docs/governance/library-home-inventory-f7.md` — file / retention / access homes
