# L-32 / WI-2 — File homes → `documents.id`

**Status:** Design note + migrate prep (schema deferred until WI-1 LIVE)  
**Date:** 2026-08-09  
**Programme:** Library spine SECOND / Identity (W-I′)  
**Depends on:** WI-1 PROD (`20261030_lib_wi1_cel` — CEL harden + scheme converge)  
**Rule:** No parallel blob SoT. Register `documents.id` is the only library file home.
F-3 / F-7 dispositions stand — enhance, never invent a new `file_path` /
`storage_key` table.

## Absolute rules

1. **Do not dual-head alembic while WI-1 (#1687) owns migrations.** The live
   schema PR for WI-2 revises `20261030_lib_wi1_cel` only after that revision is
   on `main`. A draft of that migration lives at
   `docs/governance/drafts/alembic_DRAFT_after_wi1_20261031_lib_wi2_file_homes_documents_id.py.draft`
   (``.py.draft`` — not loaded by Alembic, not under `alembic/versions/`).
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

- Upload / verify / download continue to work during dual-write window.
- Promote path (later PR, after this schema lands): create or match a Register
  `documents` row (tenant + content hash / storage key), set
  `carbon_evidence.document_id`, leave PM category / year / verification
  metadata on `carbon_evidence`.
- Match heuristics for prep dry-run (not silent auto-link in prod):
  1. Exact `file_hash` ↔ document checksum / version hash when present
  2. Same tenant + identical `storage_key` / `file_path`
  3. Else **unmatched** → steward promote queue (never invent coverage)

### UVDB (`documents_presented`)

- Element shapes observed / planned:
  - `str` — free-text title / filename (legacy)
  - `int` — already a Register id (rare)
  - `dict` with `document_id` / `id` / `title` / `name` / `label`
- Target element shape after migrate:

```json
{"document_id": 123, "label": "optional display"}
```

- Unresolvable strings stay as `{"document_id": null, "label": "<original>"}`
  until a steward files them — never silent Register create.
- CEL `evidences` links (entity = UVDB response / document) remain the coverage
  SoT once WI-1 `cover_kind` is LIVE; WI-2 does not twin coverage.

### Evidence assets

- Remain the case/investigation blob store until a later cut (F-7).
- When an asset is **filed** to the Library, set `document_id` (optional).
- Do **not** remove `storage_key` in WI-2; F-3 allowlist shrink is CUT / later.

## Prep artefacts (this branch)

| Artefact | Role |
| --- | --- |
| `scripts/governance/library/file_homes_inventory.py` | Static ORM inventory of the three homes |
| `scripts/governance/library/file_homes_migrate_prep.py` | Read-only dry-run planner over fixture / optional DB rows |
| `tests/unit/test_lib_wi2_file_homes_prep.py` | Unit pins for inventory + planner (no new alembic head) |
| Draft alembic (``.py.draft``) | Schema sketch revising WI-1 head — **not applied** |

## Exit criteria (implementing PR after WI-1 LIVE)

- [ ] Alembic revises `20261030_lib_wi1_cel` only (single head).
- [ ] `carbon_evidence.document_id` + `evidence_assets.document_id` nullable FKs.
- [ ] UVDB presented elements normalised to `{document_id, label}` projection.
- [ ] Promote / link paths are explicit steward or matched-hash — no silent Register spam.
- [ ] F-3 baseline still lists `carbon_evidence` / `evidence_assets` until a later shrink PR.
- [ ] No edits to CEL / standards.kind / catalogue_key / DocumentDetail / collaborative_*.

## References

- F-7 dispositions: `docs/governance/library-home-inventory-f7.md`
- F-3 baseline: `docs/governance/library_anti_dupe_baseline.json`
- WI-1 CEL harden: `docs/governance/library-cel-harden-d15.md`
- Conveyor: WI-2 ships L-32; depends WI-1 PROD
