# ADR-0022: Job Lifecycle Axis Vocabulary (No Second Org SSOT)

**Status**: Accepted  
**Date**: 2026-08-08  
**Decision Makers**: Product + Platform (Doc Graph × Job Lifecycle belt, Rev 2)

## Context

Job Lifecycle (JL-1+) introduces editable **job type / lane / step** axes and
cells that reference library documents (`library_document_id[]` only). Before
schema lands, we must lock how those axes relate to **organisation
vocabulary** so JL does not mint a second org system of record beside:

- Ubiquitous free-text `department: String(…)` columns on library documents,
  controlled docs, users, engineers, risks, incidents, training matrix, and
  many other modules (today’s de-facto display/filter field — **not** an FK).
- Tenant-scoped `LookupOption` rows (`lookup_options`, category + code +
  label, optional `parent_id`) used for admin-curated dropdowns. Seeded
  categories today cover workforce roles, severities, incident/complaint
  types, medical assistance, and emergency services — **not** a seeded
  `departments` category. The model docstring cites departments as an
  example category; admins may create free-form categories.

Three options were on the table for binding lanes/steps to org meaning:

1. **Bind axes to `LookupOption`** (treat lookup rows as lane/step identity).
2. **Derive axes from free-text department** strings already on modules.
3. **New Department / OrgUnit entity** (first-class org chart tables).

Belt Rev 2 already lists “new department/org-unit entity this programme” as a
**non-goal**. ADR-0021 similarly refused dual SSOTs (Doc Graph vs CEL / Golden
Thread). The same discipline applies here.

## Decision

### Locked naming

| Term | Meaning |
|---|---|
| **Job Type / Lane / Step** | JL-owned **process axes** (first-class JL tables under `job_lifecycle`). Identity is JL `code` + tenant scope — **not** an org unit. |
| **Cell** | Intersection of axes; holds `library_document_id[]` only (document SSOT remains the library `Document`). |
| **Department (platform)** | Existing free-text `department` fields on modules, and/or optional admin `LookupOption` category rows — **not** a new org entity. |
| **Org SSOT (this programme)** | **Do not create one.** JL must not become an org chart, department master, or parallel people/structure registry. |

### Axis binding (what lanes/steps *are*)

- **Job type, lane, and step rows are JL vocabulary**, authored under the
  `job_lifecycle` flag. They are process structure (Commissioning, Operate,
  …; steps within a lane), not departments.
- Axis identity **must not** be a `LookupOption.id`, must **not** be a
  free-text department string, and must **not** be a new org-unit FK.
- Cells reference library documents only — no embedded document bodies, no
  second document graph inside JL (aligns with belt non-goal “second
  document SSOT inside job cells”).

### Org / department annotation (optional, never identity)

If a lane (or job type) later needs a **department hint** for filter or
lane-level authz:

| Approach | Verdict |
|---|---|
| **New `departments` / `org_units` table** | **Rejected** for this programme. |
| **Axis identity = LookupOption** | **Rejected** — conflates process axes with curated dropdown rows; breaks when lookups are renamed/deactivated; invents org meaning where seed data does not exist. |
| **Axis identity = free-text department** | **Rejected** — unstable identity; couples JL structure to spelling drift across modules. |
| **Optional annotation only** | **Accepted.** Prefer a soft reference to `LookupOption` (`category` such as `departments`, store `code` or `lookup_option_id`) when that category is curated; otherwise optional free-text matching the existing module pattern. Annotation is nullable, non-identifying, and must not cascade-delete the axis. |

JL-1 may ship **without** any department annotation column. Adding annotation
later is additive and does not reopen this ADR unless a new org entity is
proposed (which remains out of programme scope).

### What stays unchanged

- Existing module `department` free-text columns are **not** migrated, FK’d,
  or rewritten by JL.
- `LookupOption` remains the admin dropdown SSOT for its categories; JL does
  not fork lookup tables.
- Doc Graph / Golden Thread / CEL naming and SSOTs stay as ADR-0021.

## Consequences

- JL-1 schema can land job type / lane / step / cell tables without waiting
  on an org-model programme.
- Product cannot treat swimlanes as the company org chart; UX copy should
  say “lane / step”, not “department / team”, unless an explicit annotation
  is shown.
- If Plantexpand later needs a real org-unit SSOT, that is a **separate**
  ADR and migration programme — not a silent add-on inside JL-1.
- Entity360 / hop `origin=job` producers remain references into JL axes and
  library docs — they do not invent department nodes.

## Alternatives considered

- **LookupOption-as-axis** — Rejected: process structure ≠ dropdown catalogue;
  no seeded departments category; deactivation/rename would orphan axes.
- **Free-text department-as-axis** — Rejected: no stable identity; duplicates
  and typos become structural rows; fights existing free-text sprawl instead
  of isolating JL process vocab.
- **New Department/OrgUnit entity** — Rejected for this programme (belt
  non-goal): second org SSOT beside free-text + lookups; alembic and product
  blast radius far beyond JL cells.
- **Reuse Contract / Customer as lane** — Rejected: contracts are commercial
  entities, not process steps; would create yet another overloaded axis.

## References

- Belt Rev 2 non-goals: no second document SSOT in cells; no new
  department/org-unit entity this programme.
- `LookupOption`: `src/domain/models/form_config.py`
- Lookup seeds: `src/domain/services/lookup_defaults_seed_data.py`
- Free-text department examples: `Document.department`,
  `ControlledDocument.department`, `User.department`, `Engineer.department`,
  `EnterpriseRisk.department`
- Programme flags (pre-registered default off): `job_lifecycle`,
  `job_cell_links`
- Prior SSOT discipline: `docs/adr/ADR-0021-document-relationship-graph.md`
- Library PEL / function codes (filing identity — not JL lanes): `docs/adr/ADR-0023-governance-library-reference-scheme.md`
- JL-1 depends on: this ADR merged + X-2 PROD LIVE
