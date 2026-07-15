# ADR-0018: Dual-Spine Form Builders — Admin `form_config` vs Audit Inspection Runtime

**Status**: Accepted  
**Date**: 2026-07-15  
**Decision Makers**: Platform Team (Path-11)  

## Context

The platform has two independent form-definition and runtime spines:

1. **Admin / portal spine** — `form_config` tables and `/api/v1/admin/config/templates` (+ steps/fields), edited via admin FormBuilder/FormsList.
2. **Audit inspection spine** — `audit_*` models (`AuditTemplate`, sections, questions) and `/api/v1/audits/templates` / `/api/v1/audit-templates`, edited via AuditTemplateBuilder and consumed by audit execution runtime.

PR [#1012](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1012) wires the admin FormBuilder to the `form_config` API. That work deliberately does **not** unify builders or migrate portal forms onto the audit spine.

Prior docs and UI copy sometimes implied a single “form builder.” That is inaccurate and risks wrong-schema changes (e.g. pointing incident intake at `audit_template`).

## Decision

We **lock the dual-spine model**. Two builders remain intentional until a future ADR explicitly merges them.

| Use this spine | When |
|---|---|
| **`form_config` / admin FormBuilder** | Portal and admin-configured intake for **incident**, **near-miss**, and **complaint**; contracts, lookup options, system settings tied to portal submission flows. |
| **`audit_*` / AuditTemplateBuilder** | **Audit inspections** — template authoring, section/question structure, publish/archive lifecycle, and audit run answer capture. |

### Rules

1. **No silent unification** — Do not document, label, or implement admin FormBuilder and AuditTemplateBuilder as one system. Name the spine in PRs, ledgers, and runbooks.
2. **Schema boundary** — Do not store portal intake templates in `audit_template` (or vice versa) without a migration ADR and explicit data move.
3. **#1012 scope honesty** — #1012 replaces mock admin UI state with `form_config` CRUD only; portal runtime submission paths remain on `form_config` / existing portal spine, not audit runtime.
4. **New form domains** — Choose the spine by **runtime consumer**: portal/ops intake → `form_config`; scheduled or field audit execution → `audit_*`.

## Consequences

**Positive:**
- Clear ownership reduces cross-spine regressions during admin and audit workstreams.
- #1012 and follow-on portal work can ship without blocking audit-builder evolution.

**Negative:**
- Two template models, two admin UIs, and duplicate concepts (steps/fields vs sections/questions).
- Engineers must consult this ADR before adding “generic form builder” abstractions.

## Alternatives Considered

- **Single unified builder** — Rejected for now: different lifecycles, permissions, and execution runtimes; merge cost exceeds near-term value.
- **Implicit merge via shared frontend components only** — Rejected: shared UI without schema decision preserves dual spines and hides the risk.

## References

- [#1012 — wire FormBuilder to `/admin/config/templates`](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1012) (CL-W3-FORMBUILDER-ADMIN-CONFIG)
- Routes: `src/api/routes/form_config.py`, `src/api/routes/audit_templates.py`, `src/api/routes/audits.py`
- Services: `src/domain/services/form_config_service.py`, `src/domain/services/audit_service.py`
