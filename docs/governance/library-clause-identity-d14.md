# D14 — Clause identity convergence (Library F-5)

**Status:** Design note (Accepted direction; schema lands in WI-1)  
**Date:** 2026-08-09  
**Programme:** Library spine FIRST pack (with ADR-0023 / D15 / F-7)

## Problem

QGP today has **two unjoinable ISO clause identities**:

| Identity | Where | Shape | Used by |
| --- | --- | --- | --- |
| In-memory catalogue key | `ALL_CLAUSES` / `ISOClause.id` in `src/domain/services/iso_compliance_service.py` | String e.g. `9001-7.2` | `ComplianceEvidenceLink.clause_id` (String(50)), Knowledge Bank rematch, Entity360 CEL producer, audit packs |
| ORM primary key | `clauses.id` in `src/domain/models/standard.py` | Integer FK from `controls.clause_id` | Standards Library CRUD, SoA / controls tree |

There is **no** `catalogue_key` (or equivalent) on `clauses`, so CEL rows cannot
join to the Standards / SoA tree without a brittle string parse. Building a
second “frameworks” or “coverage claims” registry would invent a **third**
identity — forbidden under the enhance-never-replicate rule.

## Decision (D14)

1. **One written key for coverage:** keep CEL’s string `clause_id` as the
   operational coverage key (matches today’s rematch / packs).
2. **Converge onto `clauses`, do not invent a second catalogue:** add
   `clauses.catalogue_key` (unique per active standard edition) equal to the
   existing `ALL_CLAUSES` / `ISOClause.id` strings.
3. **Persist the in-memory catalogue into `standards` / `clauses`:** WI-1 /
   L-27 seeds or upserts rows so `ALL_CLAUSES` becomes a loader over the DB
   catalogue, not a parallel SoT. Until then, code may keep reading
   `ALL_CLAUSES` but must not add new string-only clause stores.
4. **Do not change CEL to integer FK in the first harden PR** unless every
   writer/reader is migrated in the same change set. Preferred path:
   - add `catalogue_key`;
   - backfill from `ALL_CLAUSES`;
   - optionally add nullable `clauses_id` FK on CEL later;
   - only then consider dropping the string column.
5. **Never create** `frameworks`, `framework_requirements`, or
   `document_coverage_claims` tables as clause identity homes.

## Out of scope (this note)

- Alembic / seed implementation (WI-1).
- UVDB / Planet Mark crosswalk tables (already map via their own keys; they
  consume CEL / documents.id, not a new clause registry).
- Doc Graph edges (ADR-0021 — clause chips stay CEL composition).

## Exit criteria for implementers

- [ ] `clauses.catalogue_key` exists and is unique where not null.
- [ ] Every `ALL_CLAUSES` id has a matching `clauses` row (or an explicit
      exception list with owner).
- [ ] CEL continue to store the catalogue string; join path to SoA is
      `CEL.clause_id = clauses.catalogue_key`.
- [ ] Anti-dupe gate (F-3) still fails any new `*coverage*` / free-text
      standards twin.

## References

- CEL model: `src/domain/models/compliance_evidence.py`
- Standards ORM: `src/domain/models/standard.py`
- In-memory catalogue: `ISOComplianceService` / `ALL_CLAUSES`
- ADR-0021 (CEL owns clause links): `docs/adr/ADR-0021-document-relationship-graph.md`
- CEL harden (D15): `docs/governance/library-cel-harden-d15.md`
