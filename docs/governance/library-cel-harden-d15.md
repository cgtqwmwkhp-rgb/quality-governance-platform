# D15 — CEL harden design note (Library F-6)

**Status:** Design note (Accepted direction; schema lands in WI-1)  
**Date:** 2026-08-09  
**Programme:** Library spine FIRST pack (with ADR-0023 / D14 / F-7)

## Absolute rule

**`compliance_evidence_links` (CEL) is the coverage SoT.** Do **not** create
`document_coverage_claims`, a second confirm queue, or a frameworks twin.
Enhance CEL in place. F-3 anti-dupe already fails new `*coverage*` tables.

## Current gaps (tip `a520fb2`)

| Gap | Evidence | Why it hurts |
| --- | --- | --- |
| Unique index ignores soft-delete | `ix_cel_tenant_entity_clause` on `(tenant_id, entity_type, entity_id, clause_id)` unique, while `deleted_at` exists | Reject / soft-delete then re-link the same entity↔clause → unique violation |
| No first-class confirm provenance on the row | ORM has `created_by_*` + `status`; DTO `EvidenceLink.confirmed_by` / `confirmed_at` are derived in routes | Audit packs and “AI never silent-writes controlled truth” need durable confirmer identity |
| Coverage vs evidence relationship under-specified | `signal_type` distinguishes evidence / NC / gap / opportunity for **coverage % honesty** | Does not capture whether the document **covers** (implements / satisfies) a clause vs merely **evidences** operational proof — needed for packs and Doc Graph inheritance composition |
| Clause identity split | String `clause_id` vs `clauses.id` int | See D14 |

## Decision (D15)

### 1. Soft-delete-aware uniqueness

Replace the live unique index with a partial unique constraint (PostgreSQL):

```text
UNIQUE (tenant_id, entity_type, entity_id, clause_id)
  WHERE deleted_at IS NULL
```

Optionally include `cover_kind` in the unique key once that column lands, so one
entity may hold both a `covers` and an `evidences` row for the same clause
without collision.

**Do not** hard-delete CEL rows to “free” the unique slot.

### 2. `cover_kind`: `covers` | `evidences`

Add a required (or server-defaulted) column:

| Value | Meaning | Counts toward IMS coverage %? |
| --- | --- | --- |
| `covers` | Document / entity asserts conformance / implements the clause | Yes (subject to `signal_type` honesty rules) |
| `evidences` | Supporting proof / operational artefact for the clause | Yes only when `signal_type` is evidence/null; NC/gap/opportunity still never inflate % |

Keep existing `signal_type` for operational honesty. `cover_kind` is orthogonal:
relationship shape, not NC classification.

Default for legacy rows: `evidences` (conservative; avoids silently claiming
`covers` for historical rematch).

### 3. `confirmed_by` (and `confirmed_at`)

Persist on the CEL row (prefer `confirmed_by_id` FK → `users.id` +
`confirmed_at` timestamptz), mirrored by Doc Graph’s confirm posture
(ADR-0021):

- Propose / AI / auto paths must **not** set confirmer.
- Human confirm / manual create that lands `confirmed` must set both.
- Route serializers stop inventing confirmer from `created_by` alone once the
  columns exist (legacy backfill may copy created_by → confirmed_by only for
  historical manual confirmed rows, with an audit note).

### 4. What we never build

- `document_coverage_claims`
- `frameworks` / `framework_requirements` as coverage homes
- A third Confirm Queue (edges + CEL stay on KnowledgeExceptions / existing
  evidence confirm UI)

### 5. Version pin (already ADR-0021 P0)

Keep / complete `document_version_id` pinning so coverage cannot silently ride
a moving tip. Harden PR must not drop that column.

## Exit criteria for implementers (WI-1)

- [ ] Partial unique index live; reject→re-link integration test green.
- [ ] `cover_kind` present; legacy backfill documented.
- [ ] `confirmed_by_id` / `confirmed_at` present; AI confirm path cannot set them.
- [ ] No new coverage twin tables; F-3 gate still red on synthetics.
- [ ] D14 `catalogue_key` path documented in the same or immediately prior PR.

## References

- CEL model: `src/domain/models/compliance_evidence.py`
- Confirm provenance helper: `src/api/routes/compliance.py` (`_confirmed_provenance`)
- ADR-0021 propose→confirm: `docs/adr/ADR-0021-document-relationship-graph.md`
- Clause identity (D14): `docs/governance/library-clause-identity-d14.md`
- Anti-dupe baseline: `docs/governance/library_anti_dupe_baseline.json`
