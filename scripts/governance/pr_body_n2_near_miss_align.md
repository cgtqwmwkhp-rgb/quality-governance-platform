# Change Ledger (CL-N2-NEAR-MISS-ALIGN)

## Summary

- **Feature / Change name:** N-2 — the near-miss register runs the incident lifecycle
- **User goal:** A near miss and an incident answer "what may I do from here?" the same way, and a near miss gains the `pending_review` staging point the other registers have, so finished actions can be checked before the case is closed
- **In scope:** `20260910_nm_status_align` (data rewrite + `ck_near_misses_status`); `NearMiss` model; `NEAR_MISS_TRANSITIONS` derived from `INCIDENT_TRANSITIONS`; `CASE_CONFIGS` near-miss entry; `NearMissUpdate` pattern; near-miss/portal/H&S-import/KPI write paths; `nearMissesClient.ts` + `caseClosureClient.ts`; OpenAPI baseline and contract; unit, integration and frontend tests
- **Out of scope:** `ck_near_misses_priority` and `ck_nm_severity_values`, which are model-only in the same way and are **not** created here (see Residuals); introducing a `NearMissStatus` enum type in PostgreSQL; migrating the `priority` casing

## The problem

`near_misses.status` was the only case register storing an uppercase plain string, and the labels were not a different casing of the same lifecycle — they were a different lifecycle:

| Before | After | Why |
|---|---|---|
| `REPORTED` | `reported` | |
| `UNDER_REVIEW` | `under_investigation` | |
| `ACTION_REQUIRED` | `pending_actions` | |
| `IN_PROGRESS` | `actions_in_progress` | |
| *(absent)* | `pending_review` | actions done, awaiting a check — the register had nowhere to put this |
| `CLOSED` | `closed` | |

The edges differed too. `UNDER_REVIEW` could jump straight to `IN_PROGRESS`, and `IN_PROGRESS` could close outright — neither is legal on an incident. Reopening a closed near miss landed in `UNDER_REVIEW` rather than at the incident register's controlled `pending_review`.

The cost was spread thinly rather than concentrated anywhere obvious: an uppercase pair in `CASE_CONFIGS`, a case-insensitive `is_closed_status` for all four registers, `normalize_portal_status` existing to give the portal one casing across four tables, and a hand-written transition map that had already drifted.

## Impact Map

| Surface | Before | After |
|---|---|---|
| `near_misses.status` (data) | `REPORTED` … `CLOSED` | Rewritten to the `IncidentStatus` values by `20260910_nm_status_align` |
| `ck_near_misses_status` | Declared on the model since 20260121, **never created by any migration** — absent on every Alembic-built database | Created over the six aligned values; enforced on deployed databases for the first time |
| `NEAR_MISS_TRANSITIONS` | Hand-written uppercase map with its own edges | Derived from `INCIDENT_TRANSITIONS`, so the two registers cannot drift apart again |
| `PATCH /api/v1/near-misses/{id}` | `status` pattern `^(REPORTED\|…\|CLOSED)$` | `^(reported\|under_investigation\|pending_actions\|actions_in_progress\|pending_review\|closed)$` — a legacy uppercase label is now a 422 at the boundary |
| Reopen edge | `closed → UNDER_REVIEW` | `closed → pending_review`, identical to incidents |
| `actions_in_progress → closed` | Allowed (`IN_PROGRESS → CLOSED`) | Refused; the case must pass through `pending_review` |
| Portal track page | `IN_PROGRESS` rendered "⚙️ In Progress" | `pending_actions` / `actions_in_progress` labels added to `_STATUS_LABELS`, so the new states do not fall back to the raw key |
| FE `NEAR_MISS_STATUS_OPTIONS`, `CASE_REOPEN_STATUS`, `CASE_CLOSED_STATUS` | Uppercase near-miss entries | Lowercase; `formatCodedValue` already renders them |

## The migration, and what it refuses to do

- **Idempotent by construction.** The rewrite matches on `upper(status)`. The four labels new to this register (`under_investigation`, `pending_actions`, `actions_in_progress`, `pending_review`) never appear on the left-hand side, so a second pass cannot walk an aligned record backwards. Tested against a half-migrated table.
- **`pending_review` is added to the allowed set but no row is moved into it.** It is a state operators reach by working a case, not one that can be inferred from a record that never had it.
- **An unrecognised status raises rather than being coerced or dropped.** `UnmappedNearMissStatusError` names the value and the row count. The alternatives are worse: `ADD CONSTRAINT` fails anyway with an opaque PostgreSQL error naming neither, and skipping the constraint restores the silent model/database disagreement this migration exists to close. A governance state nobody recognises is a question for its owner, not a value a migration may invent (#1398, and the same principle as the N-1 grandfathering note).
- **`downgrade` is real but lossy in exactly one place.** It restores the uppercase labels and the uppercase constraint. `pending_review` has no pre-alignment equivalent, so those rows collapse into `IN_PROGRESS` — logged with a count, and the individual moves remain in the `near_miss.updated` audit events.

## Compatibility

- **Breaking for any client sending an uppercase near-miss status.** The API returns 422 rather than accepting it. The in-repo frontend is updated in this PR; an external caller of `PATCH /near-misses/{id}` is not.
- Reads are unaffected in shape — `status` is still a string — but the values change. `isCaseClosed` / `is_closed_status` remain case-insensitive, so a row on a database that has not yet run the migration still reads as closed and still keeps its Reopen control.
- `actions_in_progress → closed` no longer closes in one step. This is the incident rule and is deliberate; the Close dialog already reports `INVALID_STATE_TRANSITION` with `allowed_next_statuses`, so the operator is told where to go.
- No new environment flags. One Alembic revision, stacked after `20260908_soa_align` (#1530).

## Acceptance Criteria

- [x] AC-01: `NEAR_MISS_TRANSITIONS == {s.value: {t.value …} for INCIDENT_TRANSITIONS}` — asserted, not assumed
- [x] AC-02: `check_close_transition` returns the identical verdict *and* `allowed_next_statuses` for both registers, for every `IncidentStatus`
- [x] AC-03: `reopen_status_for('near_miss') == reopen_status_for('incident') == 'pending_review'`
- [x] AC-04: The migration's shipped SQL maps all five legacy labels correctly, is idempotent, and does not touch an already-aligned record
- [x] AC-05: `downgrade` restores the legacy labels and is itself idempotent
- [x] AC-06: The constraint the migration installs is exactly the set the model declares
- [x] AC-07: A legacy uppercase label is refused by `validate_near_miss_transition` rather than coerced; a legacy `CLOSED` row still reads as closed
- [x] AC-08: `openapi-baseline.json` and `docs/contracts/openapi.json` carry the pattern `app.openapi()` actually produces (verified by generating and comparing that field)
- [ ] AC-09: CI gates green on PR
- [ ] AC-10: `alembic upgrade head` on staging, then a near-miss close/reopen probe

## Testing Evidence

- [x] `pytest tests/unit/test_near_miss_incident_lifecycle_align.py` — 25 passed (new)
- [x] `pytest tests/unit/test_case_closure_gate.py tests/unit/test_case_closure_transition_parity.py tests/unit/test_case_closure_path_agreement.py tests/unit/test_portal_track_endpoint.py tests/unit/test_am_thread_case_asset_id.py` — 76 passed
- [x] `pytest tests/unit` — 5067 passed, 7 skipped, 4 failed; the four are `test_gemini_*_upstream_breaker.py` and fail identically on the base branch (pre-existing, unrelated)
- [x] `pytest tests/integration/test_near_miss_investigation.py test_portal_near_miss_fidelity.py test_portal_routing_correctness.py test_source_records_endpoint.py` — 49 passed
- [x] `pytest tests/integration/test_sibling_register_tenant_scope.py test_investigation_from_record.py test_audit_bridge_records_deletes.py test_investigation_tenant_isolation.py` — 38 passed
- [x] `npx vitest run` on the four touched frontend suites — 40 passed
- [x] `black --check` / `isort --check-only` / `flake8` on `src/`, `tests/`, the new migration — clean; `tsc --noEmit` and `eslint --max-warnings 0` clean
- [ ] Migration executed against a PostgreSQL database — **not done locally**; the rewrite SQL is exercised on SQLite, the DDL half is not

Two existing tests were strengthened rather than relaxed while being updated:

- `test_portal_track_endpoint` now covers the aligned near miss **and** keeps the legacy uppercase row as a third case, because that is what `normalize_portal_status` (PX-316) exists for.
- `CaseCloseSummaryDialog` now asserts both `closed` and legacy `CLOSED` are treated as closed, rather than only the uppercase form.

## Critical Journeys

- [x] CUJ-01: Close a near miss from `under_investigation` with lessons learnt and no open work
- [x] CUJ-02: Reopen a closed near miss — lands in `pending_review`, close stamps cleared
- [x] CUJ-03: The Close dialog's readiness read and the close itself agree on transition legality for every near-miss status
- [x] CUJ-04: Portal track of a near miss returns one casing whether the row is aligned or legacy
- [ ] CUJ-05: Staging probe after `alembic upgrade head`

## Observability

- `20260910_nm_status_align` logs the aligned set at INFO on success, and raises `UnmappedNearMissStatusError` naming the offending values and counts on refusal. A failed deploy here is the migration working.
- Expect a 422 rate on `PATCH /near-misses/{id}` if any client outside this repository still sends uppercase.
- Expect `INVALID_STATE_TRANSITION` on `actions_in_progress → closed`, which is the newly-correct refusal rather than a fault.

## Release Plan

1. Merge after #1530 (`fix/c24-soa-align-1526`), which this stacks on — the migration's `down_revision` is `20260908_soa_align`
2. `alembic upgrade head` before the API tip goes out: the new pattern refuses uppercase, and the rows must already be aligned
3. Probe a near-miss close and reopen on staging, then production

## Rollback Plan

- **Owner:** Platform / on-call release manager
- **Trigger:** Near-miss create/update failing, or the migration refusing on unmapped statuses
- **Steps:** `alembic downgrade 20260908_soa_align` (restores the uppercase labels and constraint), then revert the squash-merge commit and redeploy the previous tip. The one thing the downgrade cannot restore is `pending_review`, which collapses to `IN_PROGRESS` — check the migration's WARNING line for the count before deciding

## Residuals

- `ck_near_misses_priority` and `ck_nm_severity_values` are declared on `NearMiss` and, like `ck_near_misses_status` was, created by no migration. This PR deliberately does not create them: `priority` is still uppercase (`LOW`…`CRITICAL`) and aligning it is a separate change with its own data question. The gap is now visible rather than assumed.
- `src/domain/services/portal_service.py` is unreferenced (only `_resolve_portal_display_name` is imported, by a test). Its `_get_status_label` map was keyed on uppercase and therefore already failed for incidents, complaints and RTAs; it is lowercased here so this change does not add a near-miss regression to it, but the module's dead-code status is untouched.

## Evidence Pack

- Migration: `alembic/versions/20260910_near_miss_status_align.py`
- Unit: `tests/unit/test_near_miss_incident_lifecycle_align.py`
- OpenAPI: `openapi-baseline.json`, `docs/contracts/openapi.json`
- Docs: `docs/api/error-catalog.md` (reopen edges), `docs/data/schema-erd.md` (check constraints)
- This ledger: `scripts/governance/pr_body_n2_near_miss_align.md`

---

# Gate Checklist

- [x] **Gate 0:** Scope, Change Ledger, AC, rollback reviewed; one Alembic revision, no Alembic-on-startup
- [ ] **Gate 1:** black / isort / flake8 / mypy / OpenAPI CI green
- [x] **Gate 2:** Focused unit, integration and frontend suites green locally
- [ ] **Gate 3:** `alembic upgrade head` on staging, then a near-miss close/reopen probe
- [ ] **Gate 4:** Canary not required, but the migration must land before the API tip
- [ ] **Gate 5:** Production evidence attached post-deploy
