# CUT-1 — one retention · one Access · QGP as system of record

**Status:** Implemented — schema, resolver, filing/supersede paths and cutover gate shipped; **gate cleared by STEWARD-14 (see below)**
**Date:** 2026-08-10
**Programme:** Library spine · conveyor CUT-1 (final converge; no parallel slice) → CIT-1 (cutover)
**Depends on:** WK-1 LIVE, WJ-1 PROD — both satisfied
**ADR:** [ADR-0023](../adr/ADR-0023-governance-library-reference-scheme.md)
**Inventory:** [F-7](library-home-inventory-f7.md) §2 (retention homes) · §3 (access homes)
**Alembic head:** `20261104_lib_cut1b_drop` (revises `20261103_lib_steward14` → `20261102_lib_cut1_sor` → `20261101_lib_wj0_drop`)

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

As CUT-1 shipped: **73 filable categories — 28 executable, 31 with no disposal
clock by design, 14 blocked on a steward decision** (11 scoped clauses,
3 conditional). After STEWARD-14 (below): **42 executable, 31 clockless,
0 blocked**, and the gate runs with `--fail-on-blockers` in `CI - Default`.

## The safety invariant

Converging retention is allowed to keep documents **longer**. It is never allowed
to make one disposable earlier, because disposal is destruction.
`tests/unit/test_lib_cut1_retention_policy.py::test_cut1_never_brings_a_disposal_date_forward`
reproduces the pre-CUT-1 expression and asserts this over every rule in the
checked-in taxonomy. It holds with no exceptions. STEWARD-14 re-asserts it over
the fourteen decisions in
`test_no_decision_disposes_earlier_than_the_pre_cut1_parser`, and adds the
stronger form the decisions actually need —
`test_no_decision_is_shorter_than_the_longest_period_its_prose_names`.

`apply_supersede_retention` carries the same property into the data: it takes the
*later* of the stored date and the newly calculated one, so a legacy row whose
date was computed from approval is repaired on supersede rather than honoured.

## Resolving a blocker

A steward records `retention_years` + `retention_anchor` for the category in
`specs/governance-library/steward_retention_decisions.json`, with a short
rationale. The prose stays as written — it is the governance authority and the
R19 basis — and nothing about `taxonomy.json` needs editing to record a retention
decision.

> **Changed by STEWARD-14.** CUT-1 originally said to set the two columns on the
> `document_categories` row. That was wrong in one specific way: the seed
> re-derived both columns from prose on every run, so the next reseed, redeploy or
> admin "reload seed" erased the decision and silently re-opened the blocker on
> production while CI stayed green against the checked-in files. A database edit
> is also an unattributed retention decision, which R19 does not permit. The
> decision file is now an *input* to the seed, so a reseed restores the decision
> rather than destroying it — the same way the 06.04 deactivation list is
> reasserted. A raw database override is no longer a supported route and will be
> overwritten by the next reseed.

Filing still reads the *stored* category columns first and falls back to the
prose (`document_library_filing_service.retention_policy_for_category`). It does
not read the decision file: once the seed or `20261103_lib_steward14` has run, the
decision is on the row, and reading the file at file time too would add a third
precedence layer to a decision that already has a system of record.

## STEWARD-14 / CIT-1 — the fourteen decisions, and what that retires

All fourteen were accepted on 2026-08-10 by the Governance Library steward. The
principle applied to every one of them, and enforced by
`tests/unit/test_lib_steward14_retention_decisions.py`:

- Where the prose names more than one period, **the longest leg governs** the
  whole category. One integer cannot hold two, and keeping a record longer than
  required is recoverable — destroying it early is not.
- A period stated in months **rounds up** to the next whole year (R19 makes
  retention a count of years).
- Where the prose says the current issue is kept, the anchor is **`supersede`**,
  so a live document has no disposal date at all.
- A per-document extension the register cannot evaluate ("longer if
  incident-related", "to age 21 if a minor", "if contractual") is **not** a
  category default. It stays a steward action on the individual document.

| Category | Prose (unchanged) | Decision |
| --- | --- | --- |
| 02.02 COSHH | `Current; 40 years where linked to exposure monitoring` | 40y · supersede |
| 02.04 Method Statements & SSoW | `Current + 3 years (contract life + 6 years if contractual)` | 6y · supersede |
| 02.05 Permits to Work | `3 years (longer if incident-related)` | 3y · issue |
| 02.06 Checklists & Inspection Forms | `Completed: 3 years` | 3y · issue |
| 02.07 Incident Management | `3 years minimum (to age 21 if a minor); investigations 6 years` | 6y · issue |
| 02.08 Occupational Health | `Health records: 40 years` | 40y · issue |
| 03.04 Drills, Evacuation & PEEPs | `3 years (PEEPs: current, restricted)` | 3y · supersede |
| 04.08 Asbestos | `Register current; exposure records 40 years` | 40y · supersede |
| 04.10 Insurance | `EL certificates: 40 years recommended; others 6 years` | 40y · issue |
| 06.02 Daily Walkaround & Defect Reports | `15 months (longer if incident-related)` | 2y · issue |
| 06.04 O-Licence & Tachograph | `Tacho data 12 months; working time records 2 years` | 2y · issue |
| 07.03 External Audits & Certification | `Certificates current; reports 6 years` | 6y · supersede |
| 08.03 Waste Management | `Consignment notes 3 years; transfer notes 2 years` | 3y · issue |
| 08.04 Environmental Aspects & Spill Response | `Register current; incidents 6 years` | 6y · supersede |

`20261103_lib_steward14` writes the same fourteen onto existing
`document_categories` rows so the database matches the seed without waiting for a
reseed. It is pure data — no DDL — and touches nothing else. Downgrade returns
those fourteen to NULL, which is the state CUT-1 left them in and is the fail-safe
direction (no policy → no disposal date → kept).

### What this retires

ADR-0023 made executable retention the precondition for retiring Citation
(ATLAS)'s flat "7 Years / all employees" position. The gate now reports **zero
blockers for all 73 filable categories**, so that position is retired for the
library Register.

**There is no feature flag, and one was not invented.** Citation is an external
system that QGP does not read retention from at runtime, so a `CITATION_SOR`
boolean would be a switch with nothing on the other end — a hollow flag that
looks like control while changing no behaviour. What makes the retirement real is
executable retention on every category, the `--fail-on-blockers` gate in
`CI - Default` that keeps it that way, and the ADR-0023 amendment recording the
decision. `IMS 052` should be updated or withdrawn to match; that is a records
action outside this repository.

### The one place a document becomes disposable that was not before

Relative to **CUT-1 as it is live today**, all fourteen categories move from "no
disposal date, ever" to a calculable one. That is the intended effect — the whole
point of making retention executable — and it is why the longest-leg rule above
is enforced by test rather than by convention.

Relative to **pre-CUT-1**, thirteen of the fourteen become disposable *later* than
they already were. The exception is **06.02**, whose prose says `15 months`: the
old regex matched only `\d+ years?`, found nothing, and kept those records
indefinitely. The accepted 2 years is longer than the prose requires, but it is
the one rule where an accepted decision creates a disposal date the previous
behaviour did not have.

## CUT-1b — the second retention SoR is gone (shipped)

**Alembic:** `20261104_lib_cut1b_drop` · **Date:** 2026-08-10

CUT-1 deferred `controlled_documents.retention_period_years` "until no writer
remains". There was one, and it was not a quiet one:

```python
retention_period_years: Mapped[int] = mapped_column(Integer, default=7)
```

A SQLAlchemy `default` runs on every INSERT. Every controlled document ever
created was therefore stamped with **seven years** — Citation (ATLAS)'s flat
"7 Years / all employees" position expressed as code, on documents whose category
says three years, or forty. STEWARD-14 retired that position for the Register and
CUT-1b removes the last place it was still being written.

The single reader was `POST /document-control/{id}/obsolete`, which turned that
seven into the archive's `retention_end_date` via `timedelta(days=years * 365)` —
the same 365-day approximation, and the same made-up number.

**What replaces it.** Being marked obsolete is the document leaving the live set,
so the archive's end date is the Register's supersede-anchored answer, read
through `document_library_filing_service.supersede_retention_until` — the same
function the Register's own supersede path writes through, so the two cannot
drift. The control layer *asks*; it does not write the Register's clock, because
a second writer arriving from the other direction is the same defect.

**The answer is `NULL` whenever the Register cannot answer**: an unanchored
control record, a Register row this tenant cannot see, a legacy row filed before
CUT-1 with no policy on it, or a policy anchored on an event QGP does not hold.
Disposal hard-deletes, so an unanswerable question produces "keep". No shorter
clock was invented to fill the gap, and no flat default was reintroduced under
another name — `tests/unit/test_lib_cut1b_drop_control_retention_years.py`
asserts the control record now holds **no** retention column under any name, and
that no application code or later alembic revision names the dropped one.

The old value is deliberately **not** migrated onto the Register. It is not a
governance fact — it is a constructor default nobody chose — and copying it
forward would launder Citation's seven years into the system of record built to
replace it.

## Deliberately not in this slice

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
