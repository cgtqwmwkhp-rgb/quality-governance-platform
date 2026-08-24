# UVDB qualification scoring policy (PX-255)

Owner: Quality / UVDB (policy), Platform (implementation).

Implementation: `src/domain/uvdb/scoring_policy.py`.
Call sites: `src/api/routes/uvdb.py`.
Display layer: `frontend/src/pages/uvdbHelpers.ts`, `frontend/src/pages/UVDBAudits.tsx`.
Tests: `tests/unit/test_uvdb_scoring_policy.py`, `tests/unit/test_uvdb_score_provenance.py`,
`frontend/src/pages/__tests__/uvdbHelpers.test.ts`.

## The rule

**A protocol section contributes to a qualification percentage only if its
content is loaded. A section whose questions were never loaded is excluded from
the average, and its imported figure is cleared, never carried through as a
score.**

Where nothing assessable is scored, the qualification percentage is **absent**
(`None`), not `0.0` and not `100.0`. An empty population has no mean, and both
of the tempting substitutes are a claim: zero says "assessed and failed",
one hundred says "assessed and passed".

## Why the rule is this and not something else

Achilles UVDB Verify B2 decides whether Plantexpand can bid for utilities work.
The defect that produced this policy (PX-255) was that sections 3–11 of the
imported protocol — which carry no questions in this system and are labelled
"Questions pending PDF" — were displaying 93–100% with full green bars, and were
being averaged into a headline **99%** across AUD-2026-0042 / 0043 / 0048. Four
of the sections scoring 100% were the most safety-critical areas of the
qualification: risk assessment and safe systems of work, workplace safety,
occupational health, competence and supervision.

The original defect report called this a scoring-engine bug. It is not, and the
distinction is the reason the fix sits where it does. Those percentages are real
figures **imported from the Achilles PDF report**; nothing in this system
computed them. There is no shared scoring layer that was doing arithmetic wrong.
The defect is one of provenance and presentation: a number that came from a
report about content this system does not hold was being displayed as a live
qualification result over content it does hold. See
`docs/uat/RUN021-CODE-VERIFICATION-REVIEW.md` §2.2, which refuted the original
mechanism and rescoped the work.

So the policy is a **display and aggregation** gate, not a recalculation. The
imported figure is retained and still returned, under a different name, because
deleting an auditor's own report figure would be its own falsification.

## What "assessable" means

`section_is_assessable()`. A section is **not** assessable when any of these
holds:

- `content_status == "pending_protocol_pdf"` — the protocol shell exists, the
  questions have never been loaded;
- the section carries an empty `questions` list and a `max_score` of zero — the
  status says loaded but there is nothing in it;
- the section descriptor is missing altogether.

The last one is deliberate and is the direction to keep if this is ever
extended: an unknown section is treated as **not** assessable, so the policy
never invents assessability it cannot demonstrate. Getting that default the
other way round would reproduce PX-255 for any section the protocol index
happens not to know about.

## What the policy does to an entry

`apply_section_score_policy()` returns every entry annotated, never silently
dropped:

| Field | Assessable | Not assessable |
| --- | --- | --- |
| `assessed` | `true` | `false` |
| `excluded_from_qualification` | `false` | `true` |
| `exclusion_reason` | `null` | `pending_protocol_pdf` or `empty_section` |
| `score` / `percentage` | passed through (percentage re-derived if only score and max were supplied) | cleared to `null` |

Annotating rather than filtering is the point: the UI has to be able to say
*why* a section shows no figure, and "excluded because its questions are not
loaded" is a different statement from "scored zero" and from "not yet audited".

A `zero` mode exists for callers that would rather see a hard 0 than an
exclusion. Nothing uses it on the default path, and it is not the recommended
setting — zeroing an unassessed section is the mirror image of the original
defect, understating instead of overstating, and it is still a score where there
is no assessment.

## What the API returns

Endpoints under `/uvdb` return both numbers, with the policy's own workings
alongside them:

- `percentage_score` — the **policy-adjusted** qualification figure. This is the
  one to read as qualification.
- `report_percentage_score` — the stored import-time figure from the Achilles
  report, before exclusion. Kept for provenance and reconciliation against the
  PDF.
- `score_policy` — `policy_applied`, `included_section_numbers`,
  `excluded_section_numbers`, `fallback_to_stored`.
- `score_source` — how the displayed figure was arrived at, so the UI can label
  imported, mixed, calculated and not-scored averages differently (the PX-255
  residual, closed under the Lane 4 assurance PR).

`fallback_to_stored` is the honest failure mode: when an audit has no usable
section breakdown, the policy cannot adjust anything, so it returns the stored
figure **and says that it did**. A silent pass-through here would be the
original defect with extra steps.

The dashboard average (`GET /uvdb/dashboard`) is computed by averaging the
policy-adjusted percentage of each completed audit, not by averaging the stored
ones. Audits the policy cannot produce a figure for are left out of the mean
rather than counted as zero.

## What this policy deliberately does not do

- **It does not change stored data.** Imported section scores stay as imported.
  The exclusion is applied on read.
- **It does not decide the protocol content is wrong.** Sections pending the
  official PDF are a real state of the ingest backlog, not an error. The policy
  makes that state visible instead of scoring it.
- **It does not make the qualification figure comparable with Achilles'.** It is
  deliberately *not* the report's headline number, and the two will differ while
  sections remain unloaded. That divergence is the disclosure, not a defect —
  `report_percentage_score` is there to reconcile against.

## Changing this policy

Loading the outstanding protocol sections is what closes the gap, and it needs
no change here: a section becomes assessable the moment its questions are
loaded, and it then re-enters the average automatically. Any change to the
exclusion rule itself is a governance decision, because it changes what a
qualification percentage on a bid-relevant certification means. Record it in
this document with the same evidence: which sections, measured how, and what
the number was before and after.
