# Change Ledger (CL-CB-PR4-ASSESSMENT-OVERLAY)

> Adjacent, not fixed here: two concurrent `POST /complete` calls on one run can both pass the
> status gate. The new `source_run_id` unique constraint makes the loser's overlay savepoint fail
> (logged, assessment stands) rather than writing a twin; the same race already existed for
> `competency_records`. Not widened in this slice.

## 1) Summary
- **Feature / Change name:** CB-PR4 — bind assessment templates to a PAMS characteristic and show the demonstration on plant board cells
- **User goal:** An IT-Admin says "this assessment template proves this PAMS characteristic". A completed assessment then shows as demonstrated over the issued plant cell, and a failed one raises a revoke request instead of silently disagreeing with PAMS.
- **In scope:** `competence_assessment_binds` (1:1 template ↔ characteristic, per tenant); `competence_demonstrations` overlay rows; `POST/GET/DELETE /api/v1/workforce/competence/assessment-binds` behind the existing closed flag; additive optional `demonstrated` / `assessed_at` / `demonstrated_expires_on` on `family=pams` cells; `complete_assessment` hook that writes the overlay and opens a plant change request on fail
- **Out of scope:** Live CompetencyDashboard and any board UI; coverage quorum (CB-PR5); flag-on + ADR (CB-PR6); any PAMS write; Entra; bulk Users; fuzzy or name-based binding
- **Feature flag / kill switch:** `COMPETENCE_BOARD_ENABLED` / `FF_COMPETENCE_BOARD` stays default **false** — bind endpoints and the board are 404 while closed. Second kill switch: delete the bind row, and no further run produces an overlay. Kill SHA = previous LIVE `37f442e81006`.

## 2) Impact Map (what changed)
- **Frontend:** none. CompetencyDashboard untouched.
- **Backend:** new `competence_demonstration_service` (bind CRUD, overlay upsert, board overlay loader); `complete_assessment` calls it inside a nested savepoint after the existing `CompetencyRecord` path
- **APIs:** three new endpoints under `/workforce/competence/assessment-binds` (404 while the flag is closed); `CompetenceBoardCell` gains three optional fields, `extra="forbid"` kept on every new model
- **Database / flags:** one revision `20260901_comp_bind` on head `20260901_comp_cr`, creating `competence_assessment_binds` and `competence_demonstrations`. No existing column changed — `competency_records.asset_type_id` stays NOT NULL.
- **Workflows/jobs:** none. The PAMS snapshot beat is unchanged.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive. Unbound templates behave exactly as before; the overlay fields are absent/None when no bound run exists, never a grey `not_assessed`. Atlas cells never consult the overlay.
- **Breaking changes:** none. Clients reading `family=pams` cells see three new nullable fields.
- **Migration plan:** `alembic upgrade head` creates two empty tables, guarded by `_has_table` like CB-PR1/PR2 so a re-run is a no-op.
- **Rollback strategy (DB):** Flag off stops all reads; deleting a bind stops all future writes; `alembic downgrade 20260901_comp_cr` drops both tables. Deleting a bind deliberately does **not** delete demonstrations — competence history is kept.
- **Write-path safety:** the overlay and its change request are staged in a SAVEPOINT and committed with the assessment, so they are durable exactly when the run is. If the savepoint fails, the failure is logged and the completed assessment, its CAPA and its notification still stand — an accounting row must not be able to void a signed-off assessment.

## Compliance Delta
- **ISO 9001 7.2 / ISO 45001 7.2:** Issuance of a plant characteristic remains PAMS's record. QGP records only its own evidence that competence was demonstrated, and routes disagreement to the IT-Admin mailbox (`IT-Admin@plantexpand.com` by default) as a `revoke` change request. A failed assessment never deletes or edits issuance, and never writes PAMS.
- **What this PR does not claim:** that a revoke has been applied in PAMS; location coverage quorum (CB-PR5); a live board UI; any statutory (Atlas) overlay; that a QGP asset type and a PAMS characteristic with the same name are the same thing.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag default false. `assessment-binds` (POST/GET/DELETE) and `/board` are 404 when closed; all three routes carry the flag dependency.
- [x] AC-02: A bind is explicit — the lookup is by `template_id` + `tenant_id` only. An asset type named "Compressor" does not bind itself to the characteristic "Compressor"; with no bind row, a completed run writes no demonstration. Second template on a bound characteristic is 409, and the same pair twice is idempotent (200, not a twin).
- [x] AC-03: Completing a bound run with outcome `pass` writes one `competence_demonstrations` row keyed by characteristic (state `active`, expiry from `resolve_reassessment_interval_days`) and opens no PAMS connection and no PAMS row.
- [x] AC-04: Outcome `fail` / `conditional` writes the row as `failed` with no expiry **and** opens one open `pams` / `revoke` change request routed to the IT-Admin mailbox, quoting the failed run id. The PAMS snapshot row for that cell is neither edited nor deleted.
- [x] AC-05: `GET /board?family=pams` attaches the latest demonstration per (engineer, characteristic) to issued cells of mapped people. Cells with no run keep `demonstrated=None`; unmapped people (no `engineer_id`) never get an overlay; the query is tenant-scoped.
- [x] AC-06: `family=atlas` cells carry no demonstration — the Atlas branch never calls the overlay loader.
- [x] AC-07: The existing asset-type `CompetencyRecord` path is untouched and still writes alongside the overlay; `competency_records.asset_type_id` stays NOT NULL and the demonstration carries no asset type at all.
- [x] AC-08: The flag is not flipped, no ADR is claimed, and no coverage/quorum endpoint is added.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_competence_assessment_overlay.py` (23 tests). With `test_competence_change_requests.py`, `test_workforce_wave4_hardening.py`, `test_pams_competence_snapshot.py`, `test_atlas_competence_board.py`: 51 passed on Python 3.11. Full `tests/unit`: 7204 passed, 10 skipped, 5 failed — the same 5 (`gemini_ai` / `gemini_review` upstream breakers, `compliance_schedule_search_rbac` due-date) fail unchanged on clean `origin/main` at `37f442e81006`.
- [x] Registry guards updated, not loosened: the single-head literal in `test_job_lifecycle_ux_w4/w5.py` now names `20260901_comp_bind`, and the new `audit_templates → competence_assessment_binds` cascade is recorded in `test_delete_cascade_audit_visibility.py` (86 no-relationship pairs).
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Recording the same `source_run_id` twice updates the one demonstration — no duplicate row (unique `source_run_id` backs it).
- [x] CUJ-02: A second failed run on the same cell reuses the open revoke request; no duplicate request and no second email.
- [x] CUJ-03: An open `issue` request on that cell blocks the revoke by the CB-PR2 one-open-per-cell rule; the failed demonstration is still recorded and the completion is not turned into a 409.
- [x] CUJ-04: The overlay raising (missing table, aborted read) leaves the assessment COMPLETED, committed and notified, with a warning log and no demonstration.

## 7) Observability & Ops
- **Logs:** `Competence demonstration overlay skipped for assessment run %s; completion stands` (overlay failed — check for a missing revoke request); `Competence change request email not recorded for assessment run %s`; `competence revoke request not opened for run=... open request has a different action`.
- **Runbook:** Leave the flag false. Binds can be created while closed only by an operator with the flag on in a sandbox; with the flag false the tables simply stay empty. A demonstration against a characteristic PAMS has not issued is stored but not shown — the board overlays issued cells only.

## 8) Release Plan
- **Staging:** Flag stays false. Confirm 404 on `/api/v1/workforce/competence/assessment-binds` and `/board`. Confirm `alembic upgrade head` creates both tables and re-runs clean.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip; `COMPETENCE_BOARD_ENABLED` false; Entra attestation flag stays false.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any PAMS write or delete attributed to QGP; an assessment completion failing because of the overlay; a bind created by name rather than by explicit template id; demonstrations appearing for unmapped people.
- **Rollback steps:** Delete the bind rows (stops new overlays immediately), keep the flag false, then revert the squash on `main` and redeploy the previous LIVE SHA `37f442e81006`. `alembic downgrade 20260901_comp_cr` drops both tables if the schema must go too.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- Migration: `alembic/versions/20260901_competence_assessment_binds.py` (`20260901_comp_bind` → `20260901_comp_cr`)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (closed flag; explicit bind; additive cell fields; live page untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — flag closed)
- [x] **Gate 5:** Production verification plan + monitoring ready
