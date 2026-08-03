# ADR-0020: Compliance Schedule Occurrence Model

**Status**: Accepted  
**Date**: 2026-08-03  
**Decision Makers**: Product + Platform (Wave 0 freeze)

## Context

We need a schedule of record for **organisation- and location-level** statutory and
governance obligations (fire risk assessments, drills, EICR, LEV, insurance,
GDPR review, and similar). Five live modules already own asset-, vehicle-, and
person-scoped cadences (assets, vehicle checklists, training matrix, drivers,
inductions). The Certificates / ScheduledAudits shelves have **no create path**
and must not become a second writer.

Two occurrence designs were considered:

1. **Materialise future occurrences** as rows for a rolling horizon.
2. **Hybrid**: the requirement row holds the schedule; records are events.

## Decision

Adopt the **hybrid occurrence model**:

| Concept | Storage |
|---|---|
| Schedule | `compliance_requirements` — `next_due_date`, `last_completed_at`, `frequency_months` / `frequency_days`, `anchor` |
| Event | `compliance_records` — one row per completed **or** missed occurrence; never pre-created |
| Live status | Derived: Current / Due soon / Overdue from `next_due_date` vs injected `now` |
| Missed | A durable record outcome written by the sweep — not a status string on the requirement |

**Occurrence identity:** `UNIQUE (tenant_id, requirement_id, due_date)`.

**Anchor is data, not a code branch:**

- `completion` — next due = completion date + interval (inspections; lateness resets the clock).
- `schedule` — next due = previous due + interval (anniversaries; lateness must not drift the date).

**Boundary rule:** Compliance Schedule owns obligations whose subject is the
organisation or a location. It does **not** own per-asset LOLER/PAT/PSSR,
per-vehicle walkarounds, or per-person training / licence checks.

**Location modelling:** nullable `location_id` on the requirement (no junction).
`NULL` = organisation-wide; a value = one site.

**Why not Certificates:** Certificates have no POST writer, nullable `tenant_id`
with calendar loaders that include `IS NULL` rows, and would create a dual
system of record. Compliance Schedule is the schedule of record for org/location
obligations; library filing is a separate, explicit step (`filing_status`).

## Consequences

- Calendar and notification loaders read `next_due_date` (one row per
  requirement), avoiding horizon explosion and silent LIMIT truncation.
- Inspectors can be shown that the system knew an occurrence was missed.
- Wave 0 ships schema, catalogue, policy pure functions, flag, and kill switch
  only — no API routes.
- Status copy must never say "Expired".

## Alternatives considered

- **Materialised future occurrences** — unbounded growth, regeneration on
  frequency edits, calendar LIMIT blow-ups.
- **Pure computation with no record rows** — no durable "missed" evidence;
  notification dedupe lacks a stable identity.
- **`requirement_locations` junction** — forces one due date across sites;
  rejected after C-24 removed six dead junctions.
