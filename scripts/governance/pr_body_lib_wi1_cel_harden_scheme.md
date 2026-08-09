# Change Ledger (CL-LIB-WI1-CEL-HARDEN-SCHEME)

## 1) Summary

- **Feature / Change name:** Library spine WI-1 — CEL harden + scheme converge
  (L-26 / L-27 / L-28; D14 / D15)
- **User goal (1–2 lines):** Soft-delete / reject a coverage link and re-link the
  same entity↔clause without a unique violation; join CEL catalogue strings to
  Standards / SoA via `clauses.catalogue_key`; keep UVDB / Planet Mark identity
  on `standards` (kind=`scheme`) without inventing a frameworks twin.
- **In scope:**
  - `standards.kind` (`iso` | `scheme`) + ISO stamp + UVDB_B2 / PLANET_MARK shells
  - `clauses.catalogue_key` + upsert of every `ALL_CLAUSES` id (PG seed)
  - CEL `cover_kind` (`covers` | `evidences`, legacy default `evidences`)
  - CEL soft-delete-aware unique including `cover_kind`
  - Durable `confirmed_by_id` / `confirmed_at` + human confirm stamp; AI
    auto-confirm clears / never sets confirmer
- **Out of scope (deferred, see §3):** loading `ALL_CLAUSES` from DB at runtime
  (still reads in-memory catalogue); CEL integer FK to `clauses.id`; cloning
  UVDB B2 questions / Planet Mark categories into `clauses`; coverage % formula
  changes by `cover_kind`; W8/W9 tip-chase / explorer / nightly honesty files.
- **Feature flag / kill switch:** None — schema + writer behaviour; no new
  surface flag.

## 2) Impact Map (what changed)

- **Frontend:** None.
- **Backend:**
  - Models: `Standard.kind`, `Clause.catalogue_key`, CEL `cover_kind` /
    `confirmed_by_*`, partial unique indexes.
  - Seed helper: `src/domain/services/clause_catalogue_seed.py`.
  - Writers: `compliance.link_evidence` (cover_kind + manual confirmer stamp);
    `governed_knowledge` confirm / bulk-confirm (human confirmer stamp);
    AI `_persist_mapping` (default `evidences`, never invents confirmer).
- **APIs:** Additive response fields (`cover_kind`, `confirmed_by_id`,
  `confirmed_at`); optional request `cover_kind` on evidence link create.
- **Database:** One alembic revision `20261030_lib_wi1_cel` revising
  `20261029_lib_ns_wf_review_cycle`.
- **Config/env/flags:** None.
- **Dependencies:** None.
- **Tests:** `tests/unit/test_lib_wi1_cel_harden_scheme.py`.
- **Docs:** Design notes already on main (D14 / D15); this PR implements them.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive columns with safe defaults. CEL unique
  widens to soft-delete-aware + `cover_kind` so soft-deleted rows no longer
  block re-link; covers+evidences may coexist.
- **Breaking changes:** None for readers. Writers that insert without
  `cover_kind` get `evidences`. Lookups that ignore soft-delete continue to
  filter `deleted_at IS NULL`.
- **Migration plan:** Single serial alembic PR. PostgreSQL seeds ISO/scheme
  standards and ALL_CLAUSES catalogue keys. Legacy CEL rows backfill
  `cover_kind=evidences`; historical *manual* confirmed rows copy
  `created_by_id` → `confirmed_by_id` (AI auto-applied left without confirmer).
- **Rollback strategy (DB):** Downgrade restores the old live-blind unique and
  drops the new columns / catalogue index / kind column. Soft-deleted + live
  duplicates created after upgrade would block recreating the old unique — clear
  or hard-delete soft-deleted collisions before downgrade if any exist.

### Honest deferrals

| Concern | State after this PR |
| --- | --- |
| `ALL_CLAUSES` still in-memory SoT for rematch/packs | **Deferred.** DB catalogue is persisted and joinable; loader cutover is a follow-on once writers/readers are migrated. |
| CEL `clauses_id` integer FK | **Deferred** (D14 preferred path). |
| UVDB B2 / Planet Mark full requirement trees on `clauses` | **Deferred.** Scheme *identity* shells only; trees stay in `uvdb_*` / `planet_mark_*`. |
| Coverage % uses `cover_kind` | **Deferred.** `signal_type` honesty unchanged; `cover_kind` is relationship shape. |
| Reject route soft-deletes | **Unchanged.** Soft-delete remains DELETE `/evidence/link/{id}`; unique fix unblocks that path. |

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Coverage SoT | CEL (unique ignored soft-delete) | CEL (partial unique live + cover_kind) |
| Clause identity | `ALL_CLAUSES` string vs `clauses.id` unjoinable | `CEL.clause_id = clauses.catalogue_key` |
| Scheme registry temptation | Risk of `frameworks` twin | `standards.kind=scheme` shells only |
| Confirmer provenance | Derived / often missing on human confirm | Durable columns; human confirm stamps; AI auto-confirm does not |
| Coverage twin tables | F-3 forbids | Still forbidden; no new twin |

## 4) Acceptance Criteria (AC)

- [x] AC-01: Partial unique `ux_cel_tenant_entity_clause_cover_live` declared on
  ORM + migration DDL lockstep; soft-delete → re-link green on SQLite.
- [x] AC-02: `cover_kind` present with legacy default / backfill `evidences`;
  covers + evidences may coexist for the same entity↔clause.
- [x] AC-03: `confirmed_by_id` / `confirmed_at` present; AI auto-confirm path
  leaves them null; human confirm stamps them.
- [x] AC-04: `standards.kind` + UVDB_B2 / PLANET_MARK scheme shells planned /
  seeded (PG); no `frameworks` / `coverage_claims` table.
- [x] AC-05: Every `ALL_CLAUSES` id has a catalogue_key seed plan; PG migration
  upserts rows under matched ISO standards.
- [x] AC-06: F-3 anti-dupe gate still fails synthetics (unchanged baseline).

## 5) Testing Evidence

- Unit: `pytest tests/unit/test_lib_wi1_cel_harden_scheme.py -q` (17 passed locally)
- No existing tests weakened or skipped.

## 6) Critical Journeys

- [x] CUJ-01: Soft-delete a CEL link then re-link same entity↔clause → no unique
  violation (partial unique live rows only)
- [x] CUJ-02: Human confirm stamps `confirmed_by_id` / `confirmed_at`; AI
  auto-confirm leaves confirmer null
- [x] CUJ-03: Link with `cover_kind=covers` coexists with `evidences` for same
  entity↔clause

## 7) Observability & Ops

- Migration revision id `20261030_lib_wi1_cel` visible in alembic history
- New columns present on CEL / standards / clauses (additive)
- No new dashboards; failures surface as DB unique / API validation errors

## 8) Release Plan

1. Merge after CI green (sole alembic head)
2. Tip-chase STG → PROD; verify `build_sha` + healthz 200
3. Spot-check: soft-delete + re-link CEL; confirm stamps on human confirm

## 9) Rollback Plan (Mandatory)

- **Owner:** Library spine / Platform
- **Rollback steps:**
  1. `alembic downgrade` to `20261029_lib_ns_wf_review_cycle` on STG/PROD if
     needed (clear soft-deleted+live collisions first if any)
  2. Redeploy previous image tag if app code must roll back with schema
  3. Confirm healthz 200 and CEL link create still works under old unique

## 10) Evidence Pack

- Unit: `tests/unit/test_lib_wi1_cel_harden_scheme.py`
- Change Ledger: this body
- Migration: `alembic/versions/20261030_lib_wi1_cel_harden_scheme.py`

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger (WI-1 CEL harden only)
- [x] **Gate 1:** No frameworks twin / no coverage_claims; F-3 baseline holds
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Behaviour verified locally — unit suite green
- [x] **Gate 4:** Single serial alembic; no parallel migration PR
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed at open

## 11) Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Prod already has soft-deleted + live same key | Impossible under old unique; no demotion needed |
| Duplicate ISO standards with different codes | Matcher reuses first hit; inserts only when no match |
| OpenAPI snapshot drift | Additive fields; regenerate only if CI requires |

## 12) Merge note

W9 is LIVE (`c8934dc67`). This PR is the tip-path alembic owner — merge when
CI green; tip-chase STG+PROD. Do not parallel another migration PR.
