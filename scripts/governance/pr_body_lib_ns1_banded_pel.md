# NS-1 — Banded PEL counter + `documents.cascade_level`

## Change Ledger

| Field | Value |
|---|---|
| Wave | Northern Star **W3 / NS-1** (follows NS-0 specs, WD-1 wizard scaffold) |
| Branch | `feat/lib-ns1-banded-pel-cascade` |
| Base | `origin/main` @ `90fd36582` (NS-0 merged) |
| Migration | `20261027_lib_ns1_banded_pel` on `20261026_lib_wc1_control_holds` (single head) |
| Risk | Medium — schema re-key of a derived counter table + a behavioural tightening on upload |
| Reversible | Yes, with a documented caveat once banded references exist (§9) |
| ADR | ADR-0023 § Amendment — Northern Star (v6.0 FINAL) |
| Deferred | `owner_role` (R16), OPS→CTR+SVC reseed (Wave W2) |

## 1) Summary

Northern Star v6 (R01–R03) says a governance reference carries its cascade level
in the sequence: `PEL-HSEQ-3001` is *the* Procedure/Standard, not merely the
3001st HSEQ document. Today's allocator is per-function only and issues
`PEL-HSEQ-0001`, which cannot express a level and does not match the v6 grammar
now checked in by NS-0.

This PR makes the band load-bearing rather than cosmetic:

- `pel_doc_ref_counters` is re-keyed from `(function_id)` to
  `(function_id, level_band)`, so each of the five bands counts independently.
- `allocate_pel_doc_ref` **requires** a cascade level and emits
  `PEL-<FUNCTION>-<BAND><SEQ>` where `<BAND>` is the level digit by
  construction — R02 cannot be violated by an allocation, because the band is
  not a separate stored fact that could drift from the level.
- `documents.cascade_level` (SMALLINT, nullable, CHECK 1–5) stores the level,
  and is immutable once a PEL reference exists.

The reference is derived from the level at the moment of issue and then frozen,
which is what makes R05 (re-levelling requires a *new* reference) enforceable
instead of aspirational.

**Not in this PR, by design:** `owner_role` (R16) and the OPS→CTR+SVC function
reseed. The ADR amendment puts the reseed in Wave W2 and `owner_role` in W3–W9;
both are deliberately left alone here.

## 2) Impact Map (what changed)

| Area | Change |
|---|---|
| `src/domain/models/document_library.py` | `PelDocRefCounter` PK → `(function_id, level_band)`; `level_band` CHECK 1–5; `CASCADE_LEVELS`, `PEL_BAND_SEQ_WIDTH`, `PEL_BAND_CAPACITY` constants |
| `src/domain/models/document.py` | `cascade_level` column + CHECK + index; ORM listener refusing a level change once `pel_doc_ref` is set |
| `src/domain/services/document_category_service.py` | `coerce_cascade_level`; banded `allocate_pel_doc_ref` with band-exhaustion guard; seed writes one counter per function **per band** |
| `src/api/routes/documents.py` | `cascade_level` upload form field; refuses `function_code` without a level; returned on upload + document responses |
| `src/api/{routes,schemas}/compliance_schedule*.py` | `cascade_level` threaded through both filing paths (**forced** — see below) |
| `src/domain/services/document_register_export.py` | IMS052 gains a `Level` column (`L1`–`L5`) after `Function` |
| `frontend/src/pages/DocumentFilingFunctionStep.tsx`, `Documents.tsx`, `documentFilingWizard.ts` | Level selector in the filing wizard; Continue is disabled until a level is chosen alongside a function |
| `alembic/versions/20261027_lib_ns1_banded_pel_cascade.py` | Single revision on head `20261026_lib_wc1_control_holds` |

**On the `compliance_schedule*` diffs.** These are not unrelated drive-by
changes and cannot be dropped: both filing services call
`allocate_pel_doc_ref`, whose signature now requires a level, so omitting them
is a `TypeError` at import-exercised runtime. The only alternative was to make
those paths refuse `function_code` outright, which would withdraw a capability
WA-2 shipped. They are held to the minimum: thread a level, validate it, store
it.

## 3) Compatibility & Data Safety

- **Additive at the API.** `cascade_level` is optional everywhere; contract
  check against `origin/main`'s baseline reports **no breaking changes**. The
  one behavioural tightening is that `function_code` now demands a level —
  intended, and the whole point of the wave.
- **Existing rows are untouched.** `cascade_level` is nullable; already-issued
  `PEL-<FN>-0### ` references are **not** renumbered (R29 — append-only, and
  nothing is ever renumbered). Legacy unbanded documents render a blank Level
  in IMS052 rather than a guessed one.
- **The counter table is rebuilt, not migrated in place.** `pel_doc_ref_counters`
  is a derived high-water table whose PK changes shape; it is dropped and
  recreated, then re-seeded at `next_seq = 1` per band. This is safe *only*
  because no `PEL-<FN>-<BAND>###` reference has ever been issued — the banded
  format is introduced by this PR. Had banded references existed, seeding at 1
  would re-issue them; see the assumption note in §10.
- **Downgrade is lossy and says so.** Reverting restores the single-column
  counter at `next_seq = 1`; the pre-NS-1 sequence position cannot be recovered
  from the banded rows. `cascade_level` values are dropped with the column.

## Compliance Delta

| Rule | Before | After |
|---|---|---|
| R01 (reference grammar) | `PEL-<FN>-0001` — fails the v6 pattern | `PEL-<FN>-[1-5][0-9]{3}` — matches, pinned in test to the NS-0 rules JSON |
| R02 (band == level) | not representable | true by construction; the band is formatted from the level, not stored twice |
| R05 (re-level ⇒ reissue) | unenforceable | DB trigger + ORM listener refuse a `cascade_level` change while `pel_doc_ref` is set |
| R29 (append-only) | held | held — max+1 per band, no gap-fill, no renumbering |
| R16 (owner role) | absent | still absent — Wave W3–W9, out of scope |
| v6 function vocabulary | 11 codes incl. OPS | unchanged — reseed to CTR+SVC is Wave W2 (test records the gap explicitly) |

## 4) Acceptance Criteria (AC)

- **AC-01** Allocating with level 3 for HSEQ yields `PEL-HSEQ-3001`, and the
  next level-3 allocation yields `3002` while level 4 independently starts at
  `4001`.
- **AC-02** Allocating without a level, or with 0/6/`"x"`/`2.5`/`True`, is
  refused — no reference is issued.
- **AC-03** Uploading with `function_code` but no `cascade_level` is refused
  (400 on upload, 422 on the filing API); no document is half-created.
- **AC-04** A band that reaches 999 refuses further allocation instead of
  spilling into the next band's number space.
- **AC-05** Changing `cascade_level` on a document that already has a
  `pel_doc_ref` is refused at both the ORM and the database.
- **AC-06** IMS052 shows `L3` for a banded document and blank for a legacy one.

## 5) Testing Evidence (link to runs)

Run locally on the merge commit; CI is the authority.

- Backend unit suite: **6069 passed, 0 failed**, 10 pre-existing skips.
- `tests/unit/test_pel_doc_ref_allocation.py`: **56 passed** — format, band
  independence, level validation, exhaustion, and conformance to the checked-in
  `northern-star-rules-v6.json` (the R01 pattern and band table are *read from
  the pack*, not copied into the test).
- `tests/integration/test_compliance_schedule_filing_api.py`: **25 passed**,
  including a new test that a function without a level is refused and leaves
  the record unfiled.
- Frontend: `Documents`, `documentFilingWizard`, a11y — **26 passed**; eslint
  (0 warnings) and `tsc --noEmit` clean.
- Migration exercised on a scratch Postgres: upgrade → verify constraints,
  trigger and seeded rows → downgrade → re-upgrade.
- Gates: error-code coverage, library anti-dupe, migration naming, OpenAPI
  compatibility — all pass. Single alembic head: `20261027_lib_ns1_banded_pel`.

## 6) Critical Journeys Verified (CUJ)

- **CUJ-01** Filer uploads a document, picks Function + Level in the wizard, and
  gets a banded reference back; Continue stays disabled until the level is set,
  so the refusal is prevented in the UI rather than surfaced as a server error.
- **CUJ-02** Filer files compliance evidence to the Library with a function and
  level, and the record shows `PEL-<FN>-5001`.
- **CUJ-03** Upload with no function still succeeds with no PEL reference —
  unchanged from WD-1.
- **CUJ-04** A failed upload retried from the wizard preserves both function and
  level, so a retry cannot silently drop the band.

## 7) Observability & Ops

No new metrics or log streams. Band exhaustion and missing-level surface as
existing `ValidationError` → 400/422 paths with explicit messages naming
`cascade_level`, so they appear in existing error-rate panels. Band exhaustion
is the one to watch operationally: 999 per function per band is the ceiling the
v6 grammar imposes, and the allocator refuses rather than corrupting the format.

## 8) Release Plan

Standard governed path: merge → `CI - Default` green on tip → Azure deploy →
verify ACA image tag = tip SHA. One alembic revision runs on deploy. No feature
flag: the wizard change is inert until a filer selects a function, and the
existing `document_functions` seed already gates that.

## 9) Rollback Plan (Mandatory)

Owner: David Harris.

Rollback steps:
1. `alembic downgrade 20261026_lib_wc1_control_holds` — drops `cascade_level`
   and restores the single-column counter.
2. Revert the merge commit and redeploy.
3. **Caveat, read before rolling back:** any `PEL-<FN>-<BAND>###` reference
   issued while this was live stays on its document, but the restored counter
   is re-seeded at 1 and no longer knows about it. Re-issuing after a rollback
   could therefore collide. If references have been issued, prefer rolling
   forward with a fix over downgrading.

## 10) Evidence Pack

- `docs/adr/ADR-0023-governance-library-reference-scheme.md` § Amendment —
  Northern Star (the authority for the banded grammar).
- `specs/governance-library/northern-star-rules-v6.json` — R01 pattern and band
  table, read directly by the allocator tests.
- Migration: `alembic/versions/20261027_lib_ns1_banded_pel_cascade.py`.

**Assumption that could be wrong, stated plainly:** the counter rebuild assumes
no banded reference exists in any environment yet. That is true if this PR is
the first to ship the banded format, which the ADR and the WA-2 migration
support. If any environment somehow already holds a `PEL-<FN>-<BAND>###` row,
the re-seed at `next_seq = 1` would re-issue numbers and must be caught before
deploy — worth a one-line check against production `documents.pel_doc_ref`.

## Gate Checklist

- **Gate 0** Scope held: banded counter + `cascade_level` + level-required
  upload. `owner_role` and the W2 function reseed deliberately excluded.
- **Gate 1** Enhance never replicate: extends the WA-2 counter and the WD-1
  wizard; no twin allocator, no twin SoT, no `DocumentDetail` body edits.
- **Gate 2** Tests: banded allocator, band independence, exhaustion, level
  validation, immutability, filing refusal, IMS052 column, wizard gating. No
  test was weakened; the two wizard tests and the filing test were updated
  because the behaviour they pinned is the behaviour this PR withdraws.
- **Gate 3** Data safety: additive nullable column, append-only allocation,
  no renumbering, lossy downgrade documented.
- **Gate 4** Contract: OpenAPI regenerated, baseline synced, compatibility
  check passes against `origin/main`.
- **Gate 5** Single alembic head on tip; migration naming gate passes.
