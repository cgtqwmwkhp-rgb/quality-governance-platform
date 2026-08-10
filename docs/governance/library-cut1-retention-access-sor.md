# CUT-1 — one retention · one Access · QGP as system of record

**Status:** Implemented — schema, resolver, filing/supersede paths and cutover gate shipped
**Date:** 2026-08-10
**Programme:** Library spine · conveyor CUT-1 (final converge; no parallel slice)
**Depends on:** WK-1 LIVE, WJ-1 PROD — both satisfied
**ADR:** [ADR-0023](../adr/ADR-0023-governance-library-reference-scheme.md)
**Inventory:** [F-7](library-home-inventory-f7.md) §2 (retention homes) · §3 (access homes)
**Alembic head:** `20261102_lib_cut1_sor` (revises `20261101_lib_wj0_drop`)

## Why this slice exists

ADR-0023 decides that **QGP becomes the system of record** and that Citation
(ATLAS) "ceases to be authoritative for these documents". Its own risk register
attaches the condition that makes that sentence honest:

> *Retention becomes load-bearing the moment QGP is authoritative, but
> `retention_rule` is still free-text prose that computes nothing.* … Nothing can
> calculate a disposal date, so the 7-year Citation position is not in fact being
> replaced by anything executable. **Mitigation: treat machine-readable retention
> (`retention_years` + `retention_basis`) as a prerequisite of cutover, not a
> follow-up.**

F-7 §2 restates it as a gate and assigns the homes. Northern Star **R19** states
the rule itself: *"Retention is a number of years with a basis; a disposal date
must be calculable."*

## The defect this converge actually fixes

Before CUT-1 the whole of retention was one line:

```python
match = re.search(r"(\d+)\s*years?", category.retention_rule)
retention_until = approved_at + timedelta(days=int(match.group(1)) * 365)
```

First regex match wins, clock always starts at approval. Against the checked-in
taxonomy that produced disposal dates that are **too early**, on a queue whose
execute path hard-deletes the row, the blob and the vectors:

| Taxonomy rule | Pre-CUT-1 result | Why it was wrong |
| --- | --- | --- |
| `3 years minimum (to age 21 if a minor); investigations 6 years` | 3 years from approval | Silently dropped the six-year investigation leg |
| `Current + superseded 6 years` | 6 years from **approval** | The rule means six years after *supersede*. A document current for ten years was disposable the day it stopped being current |
| `Life of asset + 6 years` | 6 years from approval | The clock starts when the asset goes, an event QGP does not hold |
| `Tacho data 12 months; working time records 2 years` | 2 years | Two record types, two periods; one of them was simply discarded |
| `Health records: 40 years` | 40 years, ±10 days short | `timedelta(days=365*40)` drifts by the leap days |

## What CUT-1 does

### One retention

`src/domain/services/library_retention_policy.py` is now the only place prose
becomes a number and the only place a number becomes a date. Every rule resolves
to a `RetentionPolicy(years, anchor, basis)` or to a **named refusal**:

| Anchor | Meaning | Disposal date |
| --- | --- | --- |
| `issue` | Measured from approval / issue | Set at approval |
| `supersede` | Measured from the day the document left the live set | Set at supersede |
| `event` | Measured from something QGP does not hold (life of an asset, duration of employment, end of a contract) | Never — a human dates it |
| `indefinite` | No elapsed period; the current issue is kept | Never |

A rule that names two periods (`;` / `:` scoped clauses), makes the period
conditional (`longer if…`, `where…`, `recommended`, `minimum`), or states only
months is **refused with a reason** rather than reduced to whichever number a
regex found first. Thirty of the forty-four taxonomy rules resolve; fourteen are
steward decisions and are listed by the cutover gate below.

The policy is **copied onto the document when it is filed** (F-7 §2). The
document then answers for its own retention, so a later taxonomy edit cannot
silently re-date documents already filed under the old rule.
`documents.retention_until` is untouched as a concept and remains the single
disposal clock — the new columns record the policy that produced it.

Category `retention_basis` is deliberately **not** a new column: the basis *is*
`retention_rule`, and copying that prose into a second text column beside it
would be the parallel home F-7 §4 forbids. On the document the copy is real,
because it is a snapshot frozen at file time. This is the one place CUT-1 reads
F-7's wording as intent rather than literally.

### One Access

`library_rules` owns R26, so it now owns the vocabulary too:
`LIBRARY_ACCESS_LEVELS` and `normalize_access_level()`. The duplicate literal set
in `document_library_filing_service.map_category_access` is gone.

`controlled_documents.access_level` stops being a parallel vocabulary:

- A control record **anchored** to a Register row takes that row's access level.
  The Register is the SoR (F-7 §3), so a control row holding a different answer
  for the same document is the twin this converge retires.
- An unanchored record keeps its own value, folded onto the one vocabulary.
- An off-vocabulary value is **refused**, not defaulted. Defaulting would write
  an access decision nobody made.

Normalisation is **write-side only**. `user_can_read_library_document` still
compares raw values and still fails closed; normalising on read would turn a
value nobody validated into a grant. Every alias also resolves to a level at
least as restrictive as the value it replaces, so the fold cannot widen who may
read a document.

Out of scope by F-7: `documents.sensitivity`, `is_public` and `restricted_to_*`
are not listed as access homes for library filing — they serve search redaction,
not the Register ACL.

### Citation cutover gate

`scripts/governance/library/citation_cutover_readiness.py` turns ADR-0023's
condition into a runnable answer. It is static (reads `taxonomy.json`, needs no
database) and reports, per filable category, whether retention is executable,
deliberately clockless, or blocked. It never proposes a number for a blocked
category.

```
PYTHONPATH=. python3 -m scripts.governance.library.citation_cutover_readiness
```

At this commit: **73 filable categories — 28 executable, 31 with no disposal
clock by design, 14 blocked on a steward decision** (11 scoped clauses,
3 conditional).

## The safety invariant

Converging retention is allowed to keep documents **longer**. It is never allowed
to make one disposable earlier, because disposal is destruction.
`tests/unit/test_lib_cut1_retention_policy.py::test_cut1_never_brings_a_disposal_date_forward`
reproduces the pre-CUT-1 expression and asserts this over every rule in the
checked-in taxonomy. It holds with no exceptions.

`apply_supersede_retention` carries the same property into the data: it takes the
*later* of the stored date and the newly calculated one, so a legacy row whose
date was computed from approval is repaired on supersede rather than honoured.

## Resolving a blocker

A steward sets `retention_years` + `retention_anchor` on the category. The prose
stays as written — it is the governance authority and the R19 basis — and the
resolver prefers the explicit columns over its own reading. Nothing about
`taxonomy.json` needs editing to record a retention decision.

## Deliberately not in this slice

- **`controlled_documents.retention_period_years` is not dropped.** CUT-1 stops
  it being an independent SoR; the column drop waits until no writer remains.
  F-7 §2 assigns the control-layer sync to the control converge wave.
- **No backfill of `documents.retention_*` for legacy rows.** A filed document's
  retention was decided at file time; deriving it now from today's category would
  be inventing an attestation nobody made.
- **No frontend.** `Documents.tsx` does not consume `access_level` or
  `retention_until` today, and CUT-1 does not mount anything on DocumentDetail —
  WJ-1 owns that surface. Surfacing retention in the Front Sheet is a follow-up.
- **`document_access_logs` (control) is not merged** into
  `library_document_access_logs`. F-7 §3 marks it "merge writers once control
  folds", which is the control converge, not this slice.

## References

- ADR-0023 (QGP SoR + retention executable gate): `docs/adr/ADR-0023-governance-library-reference-scheme.md`
- Multi-home disposition: `docs/governance/library-home-inventory-f7.md`
- Northern Star R19 / R26 / R28: `specs/governance-library/northern-star-rules-v6.json`
- Anti-dupe baseline (unchanged by this slice): `docs/governance/library_anti_dupe_baseline.json`
