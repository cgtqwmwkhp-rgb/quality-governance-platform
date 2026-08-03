# Change Ledger (CL-B-9-SHARED-SEVERITY)

**Path claim:** `path-b9/shared-severity-negligible`

## File allowlist (exclusive)

- `alembic/versions/20260911_shared_severity_negligible.py` (new)
- `src/domain/services/shared_severity.py` (new)
- `src/domain/models/complaint.py`
- `src/domain/models/near_miss.py`
- `src/api/schemas/near_miss.py`
- `src/api/routes/complaints.py`
- `src/api/routes/near_miss.py`
- `src/api/routes/employee_portal.py`
- `src/domain/services/portal_service.py`
- `src/domain/services/lookup_enum_contract.py`
- `openapi-baseline.json`, `docs/contracts/openapi.json`
- `frontend/src/pages/Complaints.tsx`, `frontend/src/pages/ComplaintDetail.tsx`, `frontend/src/pages/NearMisses.tsx`
- `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/cy.json`
- `tests/unit/test_shared_severity_set.py` (new), `tests/integration/test_shared_severity_lookup_migration.py` (new)
- `tests/unit/test_lookup_enum_contract.py`, `tests/unit/test_wave_c2_uat_api_hygiene.py`
- `tests/integration/test_lookup_enum_contract.py`, `tests/integration/test_lookup_taxonomy_repair_migration.py`
- `tests/contract/_write_contract_baseline.py`, `tests/contract/test_write_contract_guards.py`
- `tests/test_e2e_all_workflows.py`
- `scripts/governance/pr_body_b9_shared_severity.md`

Based on `fix/c24-soa-align-1526`. Alembic head advanced by exactly one revision
(`20260908_soa_align` → `20260911_shared_severity`); no other lane holds that parent.

## 1) Summary

- **Feature / Change name:** Phase 4 B-9 — one shared severity set for the case registers
- **User goal:** `severity_levels` is a single admin lookup category feeding three
  differently-named fields — incident `severity`, complaint `priority`, near-miss
  `potential_severity`. Only incident severity accepted `negligible`, so a reporter who
  picked the option the dropdown offered got **HTTP 422** on a complaint and on a near
  miss. B-9 is the product decision that these are one severity set, not three
  taxonomies, and this change makes the database, the API and the UI agree with it.
- **In scope:** shared set `critical / high / medium / low / negligible` across incidents
  (already), complaint priority, near-miss potential severity and the portal lists; the
  two CHECK constraints; `severity_levels` registered in `ENUM_BACKED_LOOKUPS`; the last
  `KNOWN_LOOKUP_ENUM_GAPS` entry cleared.
- **Out of scope (deliberately unchanged):**
  - **RTA harm scale** (`RTASeverity`) — an injury-outcome scale derived from reported
    harm, never from a triage word.
  - **Audit finding grading** — a separate taxonomy, not fed by this lookup.
  - **`CAPAPriority`** — checked as instructed. It is a *native PostgreSQL enum type*
    (`Enum(CAPAPriority)`), not VARCHAR + CHECK, it describes action urgency rather than
    harm, and it is not populated from `severity_levels`. Different semantics, different
    shape → **left alone**.
  - **`NearMiss.priority`** (`ck_near_misses_priority`, four uppercase values) — a
    workflow queue. `near_miss_priority_for_severity()` is the documented projection from
    the five-value set onto it.
  - **`ck_incidents_severity`** — also absent from alembic-built databases, but incident
    severity already accepts all five values, so adding it is a separate repair.
- **Feature flag / kill switch:** N/A — revert commit; migration has a real `downgrade()`.

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| `ComplaintPriority` | 4 members | 5 — gains `negligible` |
| `NearMissCreate/Update.potential_severity` | hardcoded 4-value regex | pattern derived from `IncidentSeverity` |
| `ck_complaints_priority` | **declared by the model, never created by any migration** | created with the 5-value predicate |
| `ck_nm_severity_values` | **declared by the model, never created by any migration** | created with the 5-value predicate (NULL still allowed) |
| `severity_levels` lookup on a migrated DB | 4 rows — `negligible` never inserted | realigned to the 5 seeded codes, per tenant |
| Portal severity mapping | duplicated in `employee_portal.py` and `portal_service.py`, unvalidated passthrough to `potential_severity` | one `src/domain/services/shared_severity.py`; unknown words normalise to `medium` |
| Portal `/portal/config` severity list, priority labels | 4 entries | 5 |
| `KNOWN_LOOKUP_ENUM_GAPS` | 1 residual (`severity_levels`) | **empty** — every binding is now an active assertion |
| Complaint / near-miss selects (frontend) | fixed 4-option fallback | 5, matching Incidents |
| RTA severity, audit grading, CAPA priority, near-miss workflow priority | — | unchanged |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** purely widening. Every value accepted before is still
  accepted; `negligible` is added. No stored value changes meaning and no row is rewritten.
- **Two facts found while building this, both addressed in the migration:**
  1. `ck_complaints_priority` and `ck_nm_severity_values` are declared in
     `__table_args__` but **no migration has ever created them**. `complaints.priority`
     was a native enum until `20260118_enum_varchar` converted it to VARCHAR without
     adding the CHECK; `near_misses.potential_severity` has been a bare VARCHAR(20) since
     `20260121_near_miss_rta`. Only `Base.metadata.create_all` (the SQLite test path) has
     ever enforced them. This migration is therefore *widen where present, create where
     absent*, and both paths end at the same predicate.
  2. The `severity_levels` dropdown does not actually offer five options on a migrated
     database. `20260827_lookup_tenant_fix` adopts the four pre-existing orphan rows into
     the tenant, which leaves the category non-empty, and `20260828_lookup_defaults` only
     inserts into a category with no rows — so its five-row block is skipped and
     `negligible` never lands. Measured at `20260908_soa_align`: four rows. Widening the
     enums alone would not have made the option appear.
- **Lookup realignment is ledger-tracked**, the same pattern as
  `20260831_lookup_enum_align`: missing codes inserted, switched-off codes switched back
  on, codes outside the set **deactivated, never deleted** (an admin may have curated the
  label, the row may be another row's `parent_id`, and the code may appear in stored
  `form_submissions` payloads that still need to resolve to a label). Every touched row id
  is written to a `system_settings` ledger so `downgrade()` reverses exactly this
  migration's effect and nothing an administrator has done since.
- **Creating a constraint that never existed can fail on legacy rows.** The one column
  where that is plausible is `near_misses.potential_severity`: `QuickReportCreate.severity`
  is an unvalidated string and the portal wrote it through verbatim, so a client posting
  `severity: "urgent"` stored `urgent`. That intake hole is closed in this change
  (`normalize_portal_severity`), but rows written before it are **not** rewritten. The
  migration counts them and **raises `UnconstrainableSeverityValuesError` naming the
  offending values and row counts**. Silently skipping would leave the models declaring a
  constraint the database does not have — the drift `test_migration_schema_drift_lint`
  exists to catch — and guessing what `urgent` meant is not the migration's call.
- **Breaking changes:** none for clients. An operator whose `near_misses` table holds
  out-of-set severities must clean those rows before the upgrade will apply; the error
  message tells them which values and how many rows.
- **Rollback strategy:** `alembic downgrade 20260908_soa_align` (reverses the lookup rows
  through the ledger, then drops both constraints — absent *is* the previous state on
  every alembic-built database), then revert the squash commit.

## 4) Acceptance Criteria (AC)

- [x] AC-01: `POST /api/v1/complaints/` accepts `priority: "negligible"`
- [x] AC-02: `PATCH` near miss accepts `potential_severity: "negligible"`; `"extreme"` still 422
- [x] AC-03: `IncidentSeverity` and `ComplaintPriority` are member-for-member identical, enforced by test
- [x] AC-04: both CHECK constraints exist on PostgreSQL after upgrade, with the 5-value predicate
- [x] AC-05: `severity_levels` holds exactly the 5 active codes per tenant after upgrade
- [x] AC-06: upgrade **refuses** rather than skips when out-of-set rows exist
- [x] AC-07: `downgrade` restores the pre-migration lookup rows and drops both constraints
- [x] AC-08: `KNOWN_LOOKUP_ENUM_GAPS` is empty and the contract guard is an active assertion
- [x] AC-09: portal intake normalises an unrecognised severity word instead of storing it
- [x] AC-10: RTA severity, audit grading, CAPA priority, near-miss workflow priority unchanged

## 5) Testing Evidence

Run locally against PostgreSQL and SQLite:

- [x] `tests/unit/test_shared_severity_set.py` (new) — enums identical; the migration's
      inline value tuple pinned to `IncidentSeverity` so the copy cannot drift; both ORM
      CHECK predicates inspected directly; portal normalisation and the near-miss
      priority projection
- [x] `tests/integration/test_shared_severity_lookup_migration.py` (new) — insert /
      reactivate / deactivate, idempotent re-run, ledger-exact downgrade
- [x] `tests/unit/test_lookup_enum_contract.py`, `tests/integration/test_lookup_enum_contract.py`
- [x] `tests/contract/test_write_contract_guards.py` (gap list now empty)
- [x] `tests/integration/test_lookup_taxonomy_repair_migration.py`, `tests/test_e2e_all_workflows.py`,
      `tests/unit/test_migration_schema_drift_lint.py`, the `tests/contract` suite
- [x] **Real PostgreSQL exercise of the migration**, not just SQLite:
      `upgrade head` → 5 lookup rows + both constraints present + ledger row written;
      `downgrade` → 4 rows, constraints dropped, ledger removed;
      with a deliberately inserted `potential_severity='urgent'` row, `upgrade head`
      raised `UnconstrainableSeverityValuesError`, the DB stayed at `20260908_soa_align`
      and neither constraint was created; after deleting the row the upgrade succeeded
- [x] `mypy` clean; `node scripts/i18n-check.mjs` clean
- [ ] CI green — this PR

**Known pre-existing failure, not from this change:**
`tests/test_e2e_all_workflows.py::TestFormConfigWorkflow::test_public_template_access_by_slug`
fails identically on the unmodified base commit (`7c5a34bd`). Likewise the
`TestEmployeePortalWorkflows` failures in `tests/uat/test_stage1_basic_workflows.py`.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: API accepts `negligible` on complaint create and near-miss update (automated)
- [x] CUJ-02: Portal severity words resolve onto both case enums and onto the near-miss
      workflow priority, including `negligible` → `LOW` (automated)
- [x] CUJ-03: An unrecognised portal severity word normalises to `medium` rather than
      reaching the column as free text (automated)
- [x] CUJ-04: Incident severity, RTA harm scale and audit grading unchanged (automated)
- [ ] CUJ-05: **Browser, not yet run** — Complaints and Near misses create forms offer
      **Negligible** and submit 200. The frontend dependencies are not installed in this
      lane, so the three option lists and the `priority.negligible` string were changed
      but not clicked through. Needs a reviewer or staging pass.

> Note on the frontend edit: `mergeLookupSelectOptions` deliberately **overlays labels
> onto a fixed default list and does not append unknown codes**, so adding `negligible`
> to the lookup alone would never have made it appear in the complaint or near-miss
> selects. The three default lists had to gain the option for the backend change to be
> reachable by a user. Incidents already had it.

## 6b) Adjacent problems noticed, deliberately not fixed here

- `portal_service._get_priority_label()` keys its label map in **uppercase**, but three
  of its four callers pass a lowercase value (`incident.severity.value`,
  `complaint.priority.value`). Those already render the raw code rather than the emoji
  label — `critical` shows as `critical` today. Pre-existing, unrelated to severity
  membership, and changing it alters tracking-page output, so it is left alone.
  (`employee_portal.get_priority_label()` normalises casing and is correct; that is the
  one that gained `negligible`.)
- `ck_incidents_severity` is declared by the model and missing from alembic-built
  databases, exactly like the two constraints this migration installs. Incident severity
  already accepts all five values so nothing is broken by its absence, but the drift is
  real and wants its own repair.

## 7) Observability & Ops

- Migration prints the per-category counts it changed (`inserted / deactivated / reactivated`).
- Refusal path names table, column, offending values and row counts.
- Ledger row: `system_settings['migration.20260911_shared_severity.applied']`.

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Deploy; `alembic upgrade head` runs the realignment and creates both constraints
4. Staging smoke: complaint + near miss created at `negligible`; portal quick report

## 9) Rollback Plan

1. `alembic downgrade 20260908_soa_align`
2. Revert squash commit on `main`
3. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): linked after PR creation
- Builds on: PX-281/282 and #1385 (`complaint_types` / `incident_types` realignment) —
  this clears the last entry on that roadmap

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `pytest tests/unit/test_shared_severity_set.py tests/integration/test_shared_severity_lookup_migration.py`
- [ ] `pytest tests/contract tests/integration/test_lookup_enum_contract.py`
- [ ] `alembic upgrade head` then `alembic downgrade 20260908_soa_align` on a PostgreSQL copy
- [ ] Manual: create a complaint and a near miss at **Negligible**
- [ ] Manual: confirm RTA severity and audit finding grading are untouched
