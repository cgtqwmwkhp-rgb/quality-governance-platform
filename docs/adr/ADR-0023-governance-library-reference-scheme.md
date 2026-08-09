# ADR-0023: Governance Library Reference Scheme and Filing Rules

**Status**: Accepted  
**Date**: 2026-08-08  
**Decision Makers**: David Harris (IT / business owner). Decisions taken 8 August 2026.

> **Numbering:** Early drafts and a Downloads WIP used **ADR-0020** for this
> library PEL scheme. On `main`, **ADR-0020 is already the Compliance Schedule
> Occurrence Model** (`docs/adr/ADR-0020-compliance-schedule-occurrence-model.md`).
> This decision is therefore published as **ADR-0023**. Do not cite ADR-0020 for
> the library reference scheme.

## Context

The Governance Library taxonomy (Wave W0, revised in W6) allocates every filed
document a reference of the form `PEL-<SECTION>-<SUB>-<SEQ>`, derived from the
category the document sits in. Reviewing the live document estate — 309 files
across `Company Policies` and `Current PEL Documents`, reviewed 8 August 2026 —
surfaced three problems with that as designed.

**1. Documents already carry two other reference schemes.**

- `IMS ###` — 48 policies and procedures. Printed on the document face, cited in
  external audits, and listed in `IMS 052 Master Document List` (v21, 24.03.25).
  Runs IMS 001–134.
- `PLA#######` — 132 risk and COSHH assessments, allocated by the external
  assessment tool. The same tool also emits inconsistent short forms (`A`, `E`,
  `J`, `RA304`, `MVSMR`, `TWDESAL001`) on a further 28 documents.

With QGP's existing `DOC-YYYY-####` and the new `PEL-` reference, a single
document could carry four identifiers.

**2. A category-derived prefix flattens the policy set.**

All 48 policies file to `01.01 Policies` and would therefore share the prefix
`PEL-GOV-01`, whether the document governs information security, COSHH, vehicles
or data protection. The reference would carry no useful signal precisely where
the estate is most concentrated.

**3. Citation (ATLAS) and the taxonomy disagree on access and retention.**

`IMS 052` records every IMS document as living in Citation (ATLAS), access
"all employees (view only), amendments by authorised personnel", retention
"7 Years" flat. The taxonomy defaults 43 of 73 sub-categories to `managers` and
carries 44 distinct retention rules. Both cannot be authoritative.

## Decision

**Policies file to `01.01 Policies` regardless of subject.** A single, unambiguous
home; no per-document judgement call on upload. The subject is expressed through
the reference prefix and tags, not through the category.

**The reference prefix encodes the owning function, not the category.** The
reference becomes `PEL-<FUNCTION>-<SEQ>`. An information security policy filed in
`01.01` is `PEL-IT-014`; the data protection policy is `PEL-DP-007`; the company
vehicle policy is `PEL-FLT-009`.

**The function list is the 11 codes intended for
`specs/governance-library/functions.json`** (lands with the Function-axis wave;
not a second taxonomy). Derived from the management team named in IMS 001 s5.3,
the roles named in IMS 059 Communications Register, and the Control Room Manager
role profile — then reduced from 13 to 11, then to 10 when HS and CMP merged,
then back to 11 with the addition of TECH:

| Code | Function | Documents in the current estate |
| --- | --- | ---: |
| HSEQ | Health, Safety, Environment & Quality | 226 |
| IT | IT & Information Security | 21 |
| FAC | Facilities & Premises | 20 |
| PPL | People (employment + competence) | 14 |
| PROC | Procurement & Supply Chain | 12 |
| FLT | Fleet & Transport | 8 |
| OPS | Operations (incl. workshop + Control Room) | 6 |
| TECH | Technical | 1 |
| DP | Data Protection | 2 |
| FIN | Finance | 0 |
| COM | Commercial | 0 |

**The sequence is four digits and the `PEL-` company prefix is retained.** Four
digits because HSEQ holds 226 documents on day one and a two-digit sequence would
overflow immediately. The company prefix because Plantexpand documents are
submitted into client audit packs (Thames Water, UKPN, Cadent, SGN), where a bare
`IT0014` could not be asserted as Plantexpand's. The existing `IMS ###` scheme
carries a prefix for the same reason.

**The test a function has to pass:** a distinct accountable owner AND a filer able
to pick it without judgement. Where two candidates shared an owner, or produced
documents that straddled the boundary, they were merged. An ambiguous code is
worse than a coarse one, because the reference is immutable and a mis-filed one
cannot be corrected in place.

Decisions taken 8 August 2026:

- **Health & Safety owns the entire assessment estate** — every risk assessment,
  COSHH assessment, method statement and safe system of work, whoever authors it.
  The alternative (Operations owns how work is done, H&S owns hazard control)
  would have balanced at HS 32% / OPS 24%. Rejected in favour of one simple rule
  that needs no judgement and matches how the external assessment tool groups them.
- **Health & Safety, Environment and Quality are one function, HSEQ.** IMS 001
  s5.3 places all three ISO standards under a single Compliance Manager, so
  separate HS and CMP codes described two codes with one owner. The merge takes
  HSEQ to 73% of the estate. That is accepted on the basis that **the reference
  identifies and the category classifies** — 02.01 Risk Assessments, 02.02 COSHH
  and 01.01 Policies already distinguish document type, and requiring the
  reference to do it as well was what produced the artificial split. The prefix
  stays informative where it matters: IT, DP, FLT and PROC are small and specific.
- **Control Room folds into Operations.** All four of its documents are
  operational process, and their own file naming
  (`PAMS-SOP-OPS-Resource-Optimisation`) already treats it as Operations.
- **HR and Training merge into People.** Five documents straddled the old
  boundary and had been filed inconsistently: the Staff Induction Policy to
  Training, Right to Work to HR, the Training Costs Agreement — an employment
  agreement — to Training. That is the ambiguity the test is designed to catch.
- **The workshop stays in Operations, not Fleet.** Considered and rejected:
  section 06 Fleet is Plantexpand as a *vehicle operator and employer of drivers*
  (MOT and tax status, DVLA licence checks, tachograph, drivers' hours, grey
  fleet), while section 05 is the *workshop and plant* (PPM schedules, asset
  register, calibration of torque wrenches and roller brake testers, pre-use
  checks). Merging them would file a driver's licence check and a roller brake
  tester calibration certificate under one code. The only thing they share is that
  vehicles are involved.
- **Data Protection keeps its own code despite holding two documents**, because
  the DPO is expected to be independent of the function that runs the systems.
  Folding it into IT is a governance smell an auditor would notice.
- **Finance and Commercial are seeded despite owning no documents today**, so the
  first document filed under either gets the right reference rather than a
  borrowed and immutable wrong one.
- **Technical (TECH) is a separate function**, added 8 August 2026. It is the
  technical authority for the service delivered: torque and tightening standards,
  service and repair schedules, manufacturer technical data and service bulletins,
  diagnostic procedures, equipment specifications. Its boundaries are drawn
  explicitly because "technical" is the most collision-prone word in the list:
  - **not IT** — in this scheme "technical" never means computing;
  - **not OPS** — a PPM schedule *record* is Operations, the specification that
    schedule implements is Technical;
  - **not HSEQ** — how to weld safely is HSEQ, the weld specification is Technical.
  It holds one document today, `IMS134 Wheel Torque Policy`, which is a technical
  standard currently filed as a general policy. That document is a clean
  illustration of the scheme working: it stays in category `01.01 Policies`
  because it is a policy, and carries a `PEL-TECH-####` reference because the
  subject is technical.

**The function is fixed when the document is filed and never changes.** It is a
property of the document, not a live pointer to whoever currently owns it. If
information security ownership moves from the IT Manager to the DPO, existing
`PEL-IT-###` references stand unaltered. This preserves the taxonomy's rule that
a reference never encodes anything that can change, by making the function itself
a fixed attribute rather than a derived one.

**The PEL reference is the primary reference going forward.** `IMS ###` and
`PLA#######` are retained as legacy identifiers in their own field, searchable
and displayed, but are not extended — no new IMS numbers are issued.

**QGP becomes the system of record.** Citation (ATLAS) ceases to be
authoritative for these documents. The taxonomy's access defaults and retention
rules replace Citation's flat 7-year / all-staff position on migration.

### Boundary with sibling ADRs (no second SoT)

| Concern | Authority | This ADR does **not** |
| --- | --- | --- |
| Doc↔doc edges / Golden Thread naming | [ADR-0021](ADR-0021-document-relationship-graph.md) | Invent a relationship graph or rename Golden Thread |
| Job type / lane / step vs org vocabulary | [ADR-0022](ADR-0022-job-axis-vocabulary.md) | Mint a Department/OrgUnit entity or bind axes to function codes |
| Compliance Schedule occurrence / filing step | [ADR-0020](ADR-0020-compliance-schedule-occurrence-model.md) | Reuse ADR-0020 numbering or redefine occurrence identity |
| ISO clause coverage | CEL (`compliance_evidence_links`) | Invent `document_coverage_claims` or a second standards library |

Function codes classify **who owns the document for filing**. They are not Doc
Graph edge types, not JL lanes, and not ISO clause identities.

## Amendment — Northern Star (PEL-HSEQ-5014 v6.0 FINAL)

**Status**: Accepted as programme authority  
**Date**: 2026-08-09  
**Decision**: v6.0 FINAL supersedes earlier estate counts and the 11-code OPS
fold for **forward** Library work. Execution SSOT: Cursor canvas
`library-v6-northern-star-master-plan` (waves W0–W9).

### What changes

1. **Authority pack.** `specs/governance-library/northern-star-v6.json` is the
   checked-in Northern Star payload (`schema_version` 3.2,
   `final_for_app_build: true`, `allocation_frozen: true`). Slim companion:
   `northern-star-rules-v6.json` (levels, functions, R01–R32, workflow).
2. **Banded PEL.** Forward allocations match
   `^PEL-(HSEQ|IT|FAC|PPL|PROC|FLT|CTR|SVC|TECH|DP|FIN|COM)-[1-5][0-9]{3}$`
   where the first digit of the sequence is the cascade level (R01–R03). This
   tightens `PEL-<FUNCTION>-<SEQ>` without abandoning the function axis.
3. **Twelve functions.** v6 splits Operations into **CTR** (Control Room) and
   **SVC** (Service Delivery / workshop). **OPS is not in the Northern Star
   vocabulary.** Reseed is Wave **W2** (one alembic). Existing issued
   `PEL-OPS-####` rows are never silently renumbered (R29) — steward map only.
4. **Cascade level + owner role + staged rules.** Stored L1–L5, `owner_role`
   with person resolved from role assignment (R16), and R01–R32 severity
   staging are Waves **W3–W9** on the master-plan conveyor — not this docs PR.
5. **Ingest model.** Finished files are produced outside the app; QGP indexes on
   upload and provides **in-app** L1–L5 navigation (Related / PEL chips).
   Implements→standard stays CEL — never `document_edges`.

### What does not change

- Category ≠ Function; one Master Document Register; ADR-0021 edges as hierarchy
  SoT; no twin Confirm Queue / Documents-360 page; ADR-0020 remains Compliance
  Schedule only.

## Consequences

**Positive:** the reference is meaningful where the estate is most concentrated;
policies have one obvious home; ownership can be reassigned without invalidating
any reference; the legacy IMS and PLA references remain searchable so audit trails
and external citations still resolve.

**Negative / trade-offs:**

- **`PEL-HSEQ-####` will be the reference on 73% of the library.** The prefix does
  not discriminate in the one place volume is concentrated. Accepted knowingly, on
  the reasoning above: the category carries classification, and the alternative was
  two codes sharing one owner.
- `pel_doc_ref_counters` is currently one row per level-2 category. It becomes one
  row per function, and the Wave W0 migration and seeder both assume a
  category-derived prefix. Both need revising (Function-axis / WA-2 wave).
- `ref_prefix` on `document_categories` becomes a filing *default* rather than the
  determinant of the reference, which is a change in meaning for an existing column.
- The function must be captured at upload. For a bulk migration of 309 documents
  it has to be derived, and derivation will not be perfect.
- "Show me all our policies" remains one category, but "show me all IT documents"
  now spans categories and relies on the function attribute being right.

**Risks:**

- *A document is filed under the wrong function and the reference is immutable.*
  Mitigation: the function is confirmed at upload rather than inferred silently,
  and a mis-filed reference is corrected by re-filing (new reference, old one
  retired), never by editing in place.
- *Retention becomes load-bearing the moment QGP is authoritative, but
  `retention_rule` is still free-text prose that computes nothing* (44 distinct
  values, deferred in Wave W6). Nothing can calculate a disposal date, so the
  7-year Citation position is not in fact being replaced by anything executable.
  Mitigation: treat machine-readable retention (`retention_years` +
  `retention_basis`) as a prerequisite of cutover, not a follow-up.
- *`OPS` holds 6 documents and `DP` holds 2*, so a low sequence number will not
  indicate a young function — it indicates that the assessment estate was assigned
  to HSEQ. Anyone reading `PEL-OPS-0003` should not infer Operations is new or small.
- *The estate is spelled `HSQE` throughout* — in job titles, owner roles and the
  Master Document List — while the function code is `HSEQ`. The owner role has been
  renamed to `hseq-manager` / "HSEQ Manager" to match, but existing documents,
  signatures and org charts still say HSQE and will need aligning or accepting.
- *`IMS 052` is stale* — v21, March 2025, stops at IMS 128, while IMS 129, 130,
  131 and 134 exist. IMS 130 and IMS 131 are each used for two unrelated
  documents. The legacy identifier being carried across is therefore not unique.
  Mitigation: de-duplicate the IMS numbering before migration, or accept the
  legacy field is non-unique and index it as such.

## Alternatives considered

- **Keep category-derived `PEL-<SECTION>-<SUB>-<SEQ>`** — Rejected: flattens the
  policy set; encodes changeable taxonomy path into an immutable reference.
- **Publish this decision as ADR-0020** — Rejected: ADR-0020 already records the
  Compliance Schedule occurrence model on `main`.
- **Per-subject policy categories instead of function prefixes** — Rejected:
  reintroduces filer judgement and splits the single `01.01 Policies` home.

## References

- Taxonomy seed (category SSOT remains): `specs/governance-library/taxonomy.json`
- Spec pack notes: `specs/governance-library/README.md`
- Doc Graph / CEL / Golden Thread: `docs/adr/ADR-0021-document-relationship-graph.md`
- Job axis vocabulary (no second org SSOT): `docs/adr/ADR-0022-job-axis-vocabulary.md`
- Compliance Schedule (ADR-0020 — **not** this decision):
  `docs/adr/ADR-0020-compliance-schedule-occurrence-model.md`
- Clause identity convergence (D14): `docs/governance/library-clause-identity-d14.md`
- CEL harden (D15): `docs/governance/library-cel-harden-d15.md`
- Multi-home disposition (F-7): `docs/governance/library-home-inventory-f7.md`
