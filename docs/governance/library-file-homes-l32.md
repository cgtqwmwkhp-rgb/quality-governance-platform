# L-32 / WI-2 — File homes → `documents.id`

**Status:** Implemented — schema, ORM and link paths shipped  
**Date:** 2026-08-09  
**Programme:** Library spine SECOND / Identity (W-I′)  
**Depends on:** WI-1 PROD (`20261030_lib_wi1_cel` — CEL harden + scheme converge), LIVE  
**Alembic head:** `20261031_lib_wi2_homes`
(`alembic/versions/20261031_lib_wi2_file_homes_documents_id.py`)  
**Rule:** No parallel blob SoT. Register `documents.id` is the only library file home.
F-3 / F-7 dispositions stand — enhance, never invent a new `file_path` /
`storage_key` table.

## Absolute rules

1. **One alembic head.** WI-1 is LIVE on `main`, so the WI-2 revision now revises
   `20261030_lib_wi1_cel` directly and is the sole head. The prep-phase draft
   under `docs/governance/drafts/` has been retired: two files declaring
   `revision = "20261031_lib_wi2_homes"` is exactly the duplicate-source-of-truth
   the programme forbids elsewhere.
2. **Do not create** `document_coverage_claims`, frameworks twins, or a second
   Register list for PM / UVDB / case evidence.
3. **Out of scope for WI-2:** `compliance_evidence` soft-delete / `cover_kind`,
   `standards.kind`, `clauses.catalogue_key`, DocumentDetail body,
   `collaborative_*` drop (WJ-0), controlled_* fold (WC / Golden Thread already
   has `library_document_id`).

## Homes in scope

| Home | Today | WI-2 target |
| --- | --- | --- |
| `carbon_evidence` | Own `file_path` + `storage_key` blob | Nullable `document_id` FK → `documents.id`; keep PM metadata; stop treating PM blob columns as Register SoT |
| `uvdb_audit_response.documents_presented` | Untyped JSON list (titles / free refs) | Elements resolve to Register ids; JSON becomes a **projection**, not a file SoT |
| `evidence_assets` | Case-scoped `storage_key` | Optional nullable `document_id` when filed to Library; retain case store short-term |

Precedent FK name: `controlled_documents.library_document_id` (DS-5). WI-2 uses
plain `document_id` on the occurrence tables (same target: `documents.id`,
`ON DELETE SET NULL`) so PM / UVDB / case rows stay occurrence-owned.

## Link semantics

### Planet Mark (`carbon_evidence`)

- Upload / verify / download continue to work unchanged; the PM blob is still the
  read path.
- Two link paths only, both in `src/domain/services/library_file_home_link.py`:
  - **Steward** — `PATCH .../evidence/{id}` with `document_id`. The id must
    already resolve to a Register document *in the caller's tenant*; otherwise
    422 and nothing is written. `document_id: null` clears the link.
  - **Promote** — `POST .../evidence/{id}/promote-to-library` matches an existing
    Register row and links it. It never inserts into `documents`, so an unmatched
    row returns `unmatched` and stays exactly as it was.
- Match order (strongest evidence first, one candidate or nothing):
  1. `file_hash` ↔ `controlled_documents.checksum` on a control record already
     anchored to the Register by `library_document_id` (DS-5) — the Register
     itself stores no digest
  2. Same tenant + identical `storage_key` / `file_path`
  3. Else **unmatched** → steward promote queue (never invent coverage)
- Two candidates is reported `ambiguous`, not resolved by picking one.

### UVDB (`documents_presented`)

- Element shapes observed / planned:
  - `str` — free-text title / filename (legacy)
  - `int` — already a Register id (rare)
  - `dict` with `document_id` / `id` / `title` / `name` / `label`
- Target element shape after migrate:

```json
{"document_id": 123, "label": "optional display"}
```

- Normalised **on write** (`POST /uvdb/audits/{id}/responses`), not by a data
  migration: the id has to be verified against a tenant, and a migration has no
  caller tenant to verify against. Legacy rows convert the next time a response
  is written.
- Unresolvable strings stay as `{"document_id": null, "label": "<original>"}`
  until a steward files them — never silent Register create.
- A label resolves only when exactly one Register `file_name` or `title` in the
  tenant matches it. Two matches resolves to `null`, because that is the case
  where a machine choice files the wrong evidence.
- An id the tenant cannot see is demoted to its own label rather than stored, so
  a presented list can never hold a cross-tenant reference.
- CEL `evidences` links (entity = UVDB response / document) remain the coverage
  SoT once WI-1 `cover_kind` is LIVE; WI-2 does not twin coverage.

### Evidence assets

- Remain the case/investigation blob store until a later cut (F-7).
- When an asset is **filed** to the Library, set `document_id` (optional) via
  `PATCH /evidence-assets/{id}` (steward) or
  `POST /evidence-assets/{id}/promote-to-library` (proven match).
- `document_id` is deliberately **not** settable through the generic
  `PATCH /evidence-assets/{id}` field loop. That handler assigns whatever the
  update schema carries straight onto the model, so an unvalidated
  `document_id` there would write a cross-tenant Register reference. The patch
  handler routes the field through the link service instead.
- Do **not** remove `storage_key` in WI-2; F-3 allowlist shrink is CUT / later.

## Artefacts

| Artefact | Role |
| --- | --- |
| `alembic/versions/20261031_lib_wi2_file_homes_documents_id.py` | Nullable `document_id` FK + index on both occurrence tables |
| `src/domain/services/library_file_home_link.py` | The only two link paths + the UVDB projection |
| `scripts/governance/library/file_homes_inventory.py` | Static ORM inventory of the three homes |
| `scripts/governance/library/file_homes_migrate_prep.py` | Read-only dry-run planner over fixture / optional DB rows |
| `tests/unit/test_lib_wi2_file_homes_documents_id.py` | Migration chain, ORM shape, link/promote, UVDB projection |
| `tests/unit/test_lib_wi2_file_homes_prep.py` | Inventory + planner pins, now asserting the post-promotion state |

## Exit criteria

- [x] Alembic revises `20261030_lib_wi1_cel` only (single head `20261031_lib_wi2_homes`).
- [x] `carbon_evidence.document_id` + `evidence_assets.document_id` nullable FKs,
      `ON DELETE SET NULL`, indexed.
- [x] UVDB presented elements normalised to `{document_id, label}` projection.
- [x] Promote / link paths are explicit steward or matched-hash — no silent Register spam.
- [x] F-3 baseline still lists `carbon_evidence` / `evidence_assets` until a later shrink PR.
- [x] No edits to CEL / standards.kind / catalogue_key / DocumentDetail / collaborative_*.

## Deliberately still open

- No backfill. Legacy `carbon_evidence` / `evidence_assets` rows stay `NULL`
  until promoted, because nothing in the database proves a legacy row *is* a
  given Register document.
- `storage_key` / `file_path` remain on both occurrence tables and in the F-3
  allowlist. Dropping them needs every live row linked first.
- CEL `evidences` wiring for PM / UVDB occurrences (uses WI-1 `cover_kind`).

## References

- F-7 dispositions: `docs/governance/library-home-inventory-f7.md`
- F-3 baseline: `docs/governance/library_anti_dupe_baseline.json`
- WI-1 CEL harden: `docs/governance/library-cel-harden-d15.md`
- Conveyor: WI-2 ships L-32; depends WI-1 PROD
