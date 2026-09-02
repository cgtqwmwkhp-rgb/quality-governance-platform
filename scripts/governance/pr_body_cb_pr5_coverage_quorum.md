# Change Ledger (CL-CB-PR5-COVERAGE-QUORUM)

> Adjacent, not fixed here: Atlas has no Location foreign key. An Atlas person carries a free-text
> `department` string and nothing links it to `locations.id`, so an operator must set
> `match_department` on each quota by hand. A quota with no `match_department` reports `unknown`
> rather than guessing from `locations.name`. Widening Atlas to a real location FK is a separate
> track and is not attempted here.
>
> Also adjacent, not fixed: two concurrent `POST /coverage-quotas` for the same
> (tenant, location, role) can both miss the existing-row read and race into the unique constraint,
> making the loser a 500 rather than a 200. CB-PR4's `assessment-binds` has the identical shape;
> not widened in this slice.

## 1) Summary
- **Feature / Change name:** CB-PR5 — compliance-schedule coverage quorum (n of m) as a location duty
- **User goal:** A site says "we must keep at least two appointed first aiders and one fire marshal here". QGP counts who currently holds that training in the latest Atlas import, and when the count drops below the quorum the location obligation shows a coverage gap — without ever putting a named person on the compliance schedule.
- **In scope:** `competence_coverage_quotas` (one row per location × role, per tenant); an explicit Atlas `course_key` allowlist per role; `GET /api/v1/workforce/competence/coverage` plus `POST/GET/DELETE .../coverage-quotas` behind the existing closed flag; three new location-duty catalogue templates; four additive optional coverage fields on `RequirementResponse`
- **Out of scope:** CB-PR6 flag-on + ADR; CompetencyDashboard; any per-person compliance-schedule row (ADR-0020 kill); any PAMS write; bulk Users; fuzzy location↔department join; auto-creating a compliance requirement from a quota; Entra; ISO 14001 S0; Voyage V0
- **Feature flag / kill switch:** `COMPETENCE_BOARD_ENABLED` / `FF_COMPETENCE_BOARD` stays default **false** — the four coverage endpoints are 404 while closed, and the compliance schedule emits no coverage fields and issues no extra query at all. Second kill switch: delete the quota row and the overlay stops for that location. Kill SHA = previous LIVE `06de0f132ebf`.

## 2) Impact Map (what changed)
- **Frontend:** none. CompetencyDashboard untouched. No mark-applied button.
- **Backend:** new `competence_coverage_service` (role→course allowlist, quota CRUD, pure `assemble_coverage` counter, schedule overlay loader). `compliance_schedule` routes gained one flag-gated overlay lookup shared across a page of requirements.
- **APIs:** four new endpoints under `/workforce/competence` (404 while the flag is closed); `RequirementResponse` gains four optional fields; `extra="forbid"` on every new Pydantic model.
- **Database / flags:** one revision `20260901_comp_cov` on head `20260901_comp_bind`, creating `competence_coverage_quotas` and re-running the Wave 0 catalogue upsert so the three new `template_key`s land. No existing column changed.
- **Catalogue:** 25 → 28 templates, all location duties: `first_aider_coverage_quorum` (02.09), `fire_marshal_coverage_quorum` (03.04), `mhfa_coverage_quorum` (02.08). No named-person training template was added. MHFA gets a template so a `mhfa` quota cannot point at a catalogue row that does not exist.
- **Workflows/jobs:** none. The Atlas import beat and the compliance-schedule sweep are unchanged.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive. With the flag closed the schedule behaves exactly as it did at `06de0f132ebf` — `_coverage_overlay` returns before touching the database, so there is not even an extra read.
- **Breaking changes:** none. Clients reading a requirement see four new fields: three nullable, one boolean defaulting to `false`.
- **Migration plan:** `alembic upgrade head` creates one empty table, guarded by `_has_table` like CB-PR1–PR4 so a re-run is a no-op, then re-runs the existing idempotent `upsert_compliance_templates` keyed on `template_key`. Verified on SQLite: upgrade, re-run upgrade, both CHECK constraints and the uniqueness constraint enforced, downgrade clean.
- **Rollback strategy (DB):** Flag off stops all reads. Deleting a quota stops the overlay for that location and leaves every compliance requirement in place. `alembic downgrade 20260901_comp_bind` drops the quota table; it deliberately leaves the three catalogue rows, because an operator may already have activated one and dropping the template would orphan a live obligation.
- **Write-path safety:** the only writes are quota rows. A quota never creates, edits, deletes or re-dates a `ComplianceRequirement`, and never writes a `ComplianceRecord`. `next_due_date` is never derived from an Atlas expiry.

## Compliance Delta
- **ISO 45001 7.2 (competence):** the organisation determines the competence needed — the quorum on the location duty; retains documented information as evidence — the Atlas training matrix, unchanged and never written by this slice; and takes action to acquire the necessary competence — `coverage_gap` on the location obligation, which an HR Advisor answers by keeping Citation current, not by QGP editing a record.
- **Health and Safety (First-Aid) Regulations 1981 / Fire Safety Order 2005:** the duty being scheduled is the employer's duty to provide adequate first-aid and evacuation cover at the premises. It is a location obligation on purpose; the named appointed people stay on the Atlas board where their certificates live.
- **ADR-0020:** the requirement holds the schedule, records are occurrences. A coverage gap is a **second fact** on the existing location duty, not a new occurrence and not a new person-scoped requirement. `status` still derives from `next_due_date` alone.
- **What this PR does not claim:** that a gap has been remediated; that QGP has written PAMS or Citation (it has not, and cannot from this path); that an Atlas department is a location; that `FF_COMPETENCE_BOARD` should be flipped (CB-PR6); that MHFA cover is a statutory duty — its template is marked `statutory: false`.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag default false. `GET /coverage`, `POST/GET /coverage-quotas` and `DELETE /coverage-quotas/{id}` are 404 when closed; all four are declared on `_enabled_router`, which carries the flag dependency (asserted by flattening `include_router` mounts, not by reading `.path` off a wrapper).
- [x] AC-02: A person counts for a role only via an explicit `course_key` allowlist, with `passed_on` set and `expires_on` either absent or not yet past. An expired cell does not count; a cell with no `passed_on` does not count; a cell expiring today still counts. `first_aid_appointed_person_refresher` is not on the allowlist and does not count.
- [x] AC-03: People are counted, not cells — one Atlas person holding both "First Aid" and "CPR Awareness / First Aid" is one first aider. Two Atlas rows with the same display name are two people (the CB-PR3 rule holds; name is never a join key). An unmapped Atlas person (`engineer_id` null) counts, and no User is created.
- [x] AC-04: `match_department` null → `unknown`, `met` null, `gap` false, `current_m` 0 — never guessed from `locations.name`. A location named "Workshop" whose quota says `match_department="Engineer"` does not pick up the Workshop department. The comparison is exact and case-sensitive. No Atlas import → every quota `unknown` with the Atlas board's own empty banner, not an error and not zero cover.
- [x] AC-05: `POST /coverage-quotas` validates the location belongs to the tenant and fails closed with 404, disclosing nothing about the other tenant; validates `template_key` against `compliance_requirement_templates`; is idempotent for the same (tenant, location, role); rejects `required_n < 1` and an unknown `role_key` with 422 at the schema and again in the service. Unexpected body fields are 422 (`extra="forbid"`). `DELETE` is 404 for another tenant and never deletes a compliance requirement.
- [x] AC-06: A location requirement whose template matches a quota carries `coverage_gap`, `coverage_met`, `coverage_current_m`, `coverage_required_n`. `next_due_date` is unchanged, `status` is still the date-derived value, and no `ComplianceRequirement` row is created for a person. Requirements with no matching quota, no location, no template, or that are retired carry no coverage fields.
- [x] AC-07: The catalogue holds 28 templates (within the 20–30 range the loader asserts) and the three new `*_coverage_quorum` keys are present, each titled "(n of m)" and each saying in its description that named people stay on the board.
- [x] AC-08: `FF_COMPETENCE_BOARD` is not flipped, no ADR is claimed, and no per-person schedule row, PAMS write or Users create exists anywhere on this path.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_competence_coverage_quorum.py` (39 tests, all passing). With `test_atlas_competence_board.py`, `test_competence_assessment_overlay.py`, `test_job_lifecycle_ux_w4/w5.py`, `test_delete_cascade_audit_visibility.py` and `test_compliance_schedule_catalogue.py`: 205 passed on Python 3.11.
- [x] Compliance Schedule regression — every `compliance_schedule` / `fra_ocr` / `portal_fire_drill` / `incident_fra` / `executive_dashboard` unit test: 322 passed.
- [x] Full `tests/unit`: 7244 passed, 10 skipped, 4 failed — the four `gemini_ai` / `gemini_review` upstream breakers, whose traces are entirely inside `tenacity` and the AI client and touch nothing in this diff. They failed unchanged at `06de0f132ebf` (recorded in the CB-PR4 ledger).
- [x] Lint / type — `black --check src/ tests/`, `isort --check-only src/ tests/`, `flake8 src/ tests/` and `mypy src/` all clean.
- [x] Migration — exercised directly on SQLite: upgrade, re-run upgrade (no-op), `required_n >= 1` and `role_key` CHECKs both enforced, `(tenant_id, location_id, role_key)` uniqueness enforced, downgrade drops the table and leaves the catalogue rows.
- [x] Registry guards updated, not loosened: the single-head literal in `test_job_lifecycle_ux_w4/w5.py` now names `20260901_comp_cov`; the new `locations → competence_coverage_quotas` cascade is recorded in `test_delete_cascade_audit_visibility.py` (87 no-relationship pairs); the Library F-3 anti-dupe gate's `coverage_twin_table_allowlist` gains `competence_coverage_quotas` with owner and reason — headcount cover holds no standard, clause, control or evidence link, so CEL stays the coverage SoT.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: A site keeps two appointed first aiders. One certificate lapses in the weekly Atlas upload; `current_m` drops to 1, `met` becomes false and the location duty reports `coverage_gap`. `next_due_date` does not move and no new row appears anywhere.
- [x] CUJ-02: Creating a quota does not create a compliance requirement. The operator still activates the location obligation from the catalogue; the quota is the bind, the schedule row is independent, and `GET /coverage` answers correctly with no requirement row at all.
- [x] CUJ-03: The same quota posted twice updates the one row and answers 200, not a twin and not a 409.
- [x] CUJ-04: With no Atlas import at all, `GET /coverage` returns every quota as `unknown` with the Atlas empty banner. Nothing reads as "zero first aiders" because nobody has uploaded a spreadsheet.
- [x] CUJ-05: With the flag closed, `GET /requirements` is byte-identical to today apart from the four defaulted fields, and the coverage lookup never opens a query.

## 7) Observability & Ops
- **Logs:** the migration logs `20260901_comp_cov: upserted 28 compliance requirement templates`, and skips the upsert with a log line if Wave 0 has not run. The read path adds no logging — it has no failure mode of its own beyond the database.
- **Runbook:** Leave the flag false. Quotas can only be created with the flag open in a sandbox; with it false the table stays empty and the schedule is unaffected. `match_department` must be typed exactly as Atlas stores it (case-sensitive) — an unset or mistyped department shows as `unknown`, which is the intended honest answer rather than a silent zero. To retire a duty, delete the quota; the location obligation on the schedule is unaffected and must be deactivated separately if that is also wanted.

## 8) Release Plan
- **Staging:** Flag stays false. Confirm 404 on `/api/v1/workforce/competence/coverage` and `/coverage-quotas`. Confirm `GET /api/v1/compliance-schedule/requirements` returns no coverage fields set. Confirm `alembic upgrade head` creates the table, lands the three catalogue rows, and re-runs clean.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip; `COMPETENCE_BOARD_ENABLED` false; Entra attestation flag stays false.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** any per-person compliance-schedule row attributable to coverage; any `next_due_date` moved by an Atlas expiry; any PAMS or Citation write; a quota counting a person whose department was never mapped; a coverage lookup firing while the flag is closed.
- **Rollback steps:** Delete the quota rows (stops every overlay immediately), keep the flag false, then revert the squash on `main` and redeploy the previous LIVE SHA `06de0f132ebf`. `alembic downgrade 20260901_comp_bind` drops the quota table if the schema must go too; the three catalogue templates stay by design.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- Migration: `alembic/versions/20260901_competence_coverage_quotas.py` (`20260901_comp_cov` → `20260901_comp_bind`)
- Catalogue: `specs/compliance-schedule/catalogue.json` (25 → 28 location-duty templates)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (closed flag; explicit department bind; additive requirement fields; ADR-0020 held; live page untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — flag closed)
- [x] **Gate 5:** Production verification plan + monitoring ready
