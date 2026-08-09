# Change Ledger (CL-LIB-WI2-FILE-HOMES-DOCUMENTS-ID)

## 1) Summary

- **Feature / Change name:** Library spine WI-2 — occurrence file homes →
  `documents.id` (L-32; F-3 / F-7)
- **User goal (1–2 lines):** Let a steward say "this Planet Mark evidence / case
  asset / presented document *is* that Register document", so the Library can
  answer what is filed without a second blob source of truth — and make it
  impossible to fabricate that answer.
- **In scope:**
  - Nullable `document_id` FK (`ON DELETE SET NULL`, indexed) on
    `carbon_evidence` and `evidence_assets`
  - `uvdb_audit_response.documents_presented` converges on a
    `{document_id, label}` projection, normalised on write
  - `src/domain/services/library_file_home_link.py` — the only two link paths:
    steward-named id, or a proven content match
  - Steward `PATCH` + explicit `POST .../promote-to-library` on both occurrence
    surfaces; promote never inserts into `documents`
- **Out of scope (deferred, see §3):** backfill of legacy NULL links; dropping
  `storage_key` / `file_path` from the occurrence tables and shrinking the F-3
  allowlist; CEL `evidences` wiring for PM / UVDB occurrences; `collaborative_*`
  drop (WJ-0); DocumentDetail body.
- **Feature flag / kill switch:** None. The column is nullable and unread by any
  existing path, so "off" is the pre-existing behaviour.

## 2) Impact Map (what changed)

- **Frontend:** None.
- **Backend:**
  - Models: `CarbonEvidence.document_id`, `EvidenceAsset.document_id`.
  - Service: `src/domain/services/library_file_home_link.py` (link, promote,
    match, UVDB projection). Reads only — the routes own the commit.
  - Routes: `planet_mark.patch_evidence` (+ `document_id`),
    `planet_mark.promote_evidence_to_library` (new),
    `evidence_assets.update_evidence_asset` (+ `document_id`, routed out of the
    generic assign loop), `evidence_assets.promote_asset_to_library` (new),
    `uvdb.create_response` (normalises presented list on write).
- **APIs:** Additive only. Two new `POST .../promote-to-library` endpoints; new
  optional request field `document_id`; new response fields `document_id` /
  `documents_presented`. No field removed, none made required.
- **Database:** One alembic revision `20261031_lib_wi2_homes`
  (`alembic/versions/20261031_lib_wi2_file_homes_documents_id.py`) revising
  `20261030_lib_wi1_cel` — sole head. No data migration.
- **Config/env/flags:** None.
- **Dependencies:** None.
- **Tests:** `tests/unit/test_lib_wi2_file_homes_documents_id.py` (new, 47);
  `tests/unit/test_lib_wi2_file_homes_prep.py` (inverted to pin post-promotion
  state); alembic head pins in `test_job_lifecycle_ux_w4/w5.py`.
- **Docs:** `docs/governance/library-file-homes-l32.md` moves from design note to
  implemented; the prep-phase `.py.draft` is retired.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Purely additive. Both columns are nullable with no
  default and no backfill; every existing reader and writer is untouched.
- **Breaking changes:** None. `documents_presented` gains a normalised shape on
  *new* writes only; the reader already treats the field as opaque JSON, and
  legacy element shapes (bare title, bare id, `{id,title}`) are still accepted on
  the way in.
- **Migration plan:** Single serial alembic revision. Add column, FK and index on
  two tables, guarded by inspector checks so a partially-applied environment is
  idempotent. No row is written.
- **Rollback strategy (DB):** `alembic downgrade 20261030_lib_wi1_cel` drops the
  index, constraint and column in reverse order. Only the links are lost; no
  occurrence row, blob, or Register document is affected. Presented lists already
  normalised stay `{document_id, label}` — that shape is valid legacy JSON and is
  re-read correctly by the pre-WI-2 code, which treats the field as opaque.

### Honest deferrals

| Concern | State after this PR |
| --- | --- |
| Legacy rows have no `document_id` | **Deferred by design.** Nothing in the DB proves a legacy row *is* a given Register document. Guessing from a filename would file coverage nobody attested to. |
| `storage_key` / `file_path` still on occurrence tables | **Deferred.** F-3 allowlist shrink needs every live row linked first. |
| Legacy `documents_presented` rows not converted | **Deferred.** Resolving an id needs a caller tenant; a data migration has none. Rows convert on next write. |
| Content-hash match only covers controlled documents | **Known limit.** The Register stores no digest; the only hash is `controlled_documents.checksum` on a record already anchored by `library_document_id` (DS-5). Uncovered documents fall through to path match, then to the steward queue. |
| CEL `evidences` wiring for PM / UVDB occurrences | **Deferred** (uses WI-1 `cover_kind`). |

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Library file home | `carbon_evidence` / `evidence_assets` blobs unjoinable to Register | Nullable `document_id` → `documents.id`; Register remains the only home |
| Second blob SoT (F-3 / F-7) | Risk of a new `file_path` twin table | No new table; link only, occurrence blobs untouched |
| Silent Register create | Upload paths could conjure a filed document | Promote never inserts into `documents`; enforced on the AST |
| Cross-tenant reference | An `document_id` in a PATCH body would be stored unchecked | Every id verified in the caller's tenant or rejected |
| Machine-guessed coverage | Filename similarity could auto-link | Two candidates → `ambiguous`, never resolved by picking one |
| Register document deletion | n/a | `ON DELETE SET NULL` — the occurrence row and its metadata survive |

## 4) Acceptance Criteria (AC)

- [x] AC-01: Single alembic head `20261031_lib_wi2_homes` revising
  `20261030_lib_wi1_cel`; no sibling revision sits on the WI-1 head.
- [x] AC-02: `carbon_evidence.document_id` and `evidence_assets.document_id` are
  nullable, indexed, `ON DELETE SET NULL`; ORM constraint/index names are in
  lockstep with the migration.
- [x] AC-03: `documents_presented` elements project to `{document_id, label}`;
  an unresolvable title keeps its label with a null id.
- [x] AC-04: Link paths are steward-named or proven-match only. Promote on an
  unmatched file returns `unmatched`, writes nothing, and creates no `documents`
  row (asserted by row count, and structurally on the AST).
- [x] AC-05: An id belonging to another tenant is rejected
  (`DOCUMENT_NOT_FOUND`, 422) and a cross-tenant id in a presented list is
  demoted to a label rather than stored.
- [x] AC-06: The migration performs no backfill — enforced by an AST pin on the
  `op.*` calls it is allowed to make.
- [x] AC-07: Occurrence blob columns (`storage_key`, `file_path`,
  `checksum_sha256`) survive; F-3 allowlist unchanged.

## 5) Testing Evidence

- Unit (new): `pytest tests/unit/test_lib_wi2_file_homes_documents_id.py -q`
  → **47 passed**. Link and projection tests run against a real in-memory
  SQLite session, not mocks: the property under test is that a query is
  tenant-scoped, and a mock returns what it was told regardless of the WHERE
  clause it was handed.
- Mutation-checked (guards proven non-vacuous): removing the tenant filter from
  `register_document_exists` fails 3 tests; removing it from the blob-path match
  fails 1; removing the ambiguity guard fails 1. Restored after checking.
- Full unit suite: `pytest tests/unit/ -q --cov=src --cov-fail-under=48`
  → **6290 passed, 11 skipped**, coverage **64.47%**.
- Gates run locally: `black --check`, `isort --check-only`, `flake8` (0),
  `mypy src/` (no issues, 598 files), `validate_migration_naming.py`
  (253 migrations, 0 violations), `validate_schema_constraints.py`
  (no critical violations).
- No existing test weakened or skipped. `test_lib_wi2_file_homes_prep.py`
  assertions that held the prep phase open ("no live WI-2 alembic",
  "carbon_evidence still needs a FK") are **inverted, not relaxed** — each now
  asserts the stronger post-promotion fact.

## 6) Critical Journeys

- [x] CUJ-01: Steward PATCHes `document_id` onto Planet Mark evidence → linked;
  the same id from another tenant → 422 and nothing written.
- [x] CUJ-02: Promote an evidence asset whose checksum is already on the Register
  → linked by `content_hash`; promote one that is not → `unmatched`, asset
  unchanged, Register unchanged.
- [x] CUJ-03: UVDB response presenting a known title → `{document_id, label}`;
  presenting an unfiled title → `{document_id: null, label: "<original>"}`.
- [x] CUJ-04: Clearing a wrong link (`document_id: null`) removes the claim and
  leaves the occurrence blob and metadata intact.

## 7) Observability & Ops

- Migration revision `20261031_lib_wi2_homes` visible in alembic history.
- Every written match logs at INFO with the occurrence id, `documents.id` and the
  method that proved it (`content_hash` / `storage_path`) — a link is auditable
  back to its evidence.
- Promote responses return `status` + `method` + `detail` rather than a bare
  boolean, so `unmatched` and `ambiguous` are distinguishable to a steward; the
  second means the Register already holds two candidates.
- Coverage of unlinked rows is observable via
  `scripts/governance/library/file_homes_inventory.py`.

## 8) Release Plan

1. Merge after CI green (sole alembic head).
2. Tip-chase STG → PROD; verify `build_sha` + healthz 200.
3. Verify ACA image tag contains the tip SHA before calling it LIVE.
4. Spot-check: PATCH a `document_id`, promote a matched and an unmatched row,
   POST a UVDB response with a known and an unknown title.

## 9) Rollback Plan (Mandatory)

- **Owner:** Library spine / Platform
- **Rollback steps:**
  1. `alembic downgrade 20261030_lib_wi1_cel` on STG/PROD — drops index, FK and
     column in reverse order; no occurrence row or blob is touched.
  2. Redeploy the previous image tag if app code must roll back with the schema.
  3. Confirm healthz 200, evidence upload/verify/download still work, and a UVDB
     response still records.

## 10) Evidence Pack

- Migration: `alembic/versions/20261031_lib_wi2_file_homes_documents_id.py`
- Service: `src/domain/services/library_file_home_link.py`
- Unit: `tests/unit/test_lib_wi2_file_homes_documents_id.py`,
  `tests/unit/test_lib_wi2_file_homes_prep.py`
- Design note: `docs/governance/library-file-homes-l32.md`
- Change Ledger: this body

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger (WI-2 file homes only)
- [x] **Gate 1:** No second blob SoT, no `document_coverage_claims`, no
  frameworks twin; F-3 baseline holds
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Behaviour verified locally — new module + full unit suite green
- [x] **Gate 4:** Single serial alembic; no parallel migration PR
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed at open

## 11) Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| A steward links the wrong document | `document_id: null` clears it; the cleared id is returned so it can be audited |
| Two Register documents share a blob path | Reported `ambiguous`; no link written |
| Presented list re-normalised repeatedly | Projection is stable on reapply (pinned by test) |
| Unexpected legacy `documents_presented` scalar | Non-list values pass through untouched rather than being rewritten — it is the only copy |
| OpenAPI snapshot drift | Additive only; the compatibility checker treats new endpoints and optional fields as non-breaking |
| SQLite cannot `ADD CONSTRAINT` | Migration lands column + index and logs the skip; PostgreSQL everywhere that matters |

## 12) Merge note

WI-1 is LIVE (`e8fbfe438e2`, STG + PROD). This PR is the tip-path alembic owner
and revises `20261030_lib_wi1_cel` as the sole head — merge when CI is green,
then tip-chase STG + PROD. Do not open a parallel migration PR. Not DONE until
the ACA image tag is verified as the tip SHA.
