# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Compliance Schedule → CAPA from a failed check (W18)
- **User goal (1–2 lines):** When an obligation is closed with a failed check, the
  corrective action it owes exists automatically, is assigned to the obligation
  owner, and is reachable from the Actions register with a link back to the
  obligation.
- **In scope:** `CAPAAutoService.create_from_compliance_record`; the
  `ComplianceScheduleService.complete_requirement` hook; the `compliance_record`
  source on the unified Actions filter and the Actions/ActionDetail source link
  and label helpers; tests.
- **Out of scope:** calendar feed, library filing bridge, Export Center, the
  missed-occurrence sweep (it writes `outcome=missed`, not a failed check), and
  any change to `RecordResponse` — the compliance detail page does not yet show
  the CAPA it raised.
- **Feature flag / kill switch:** `COMPLIANCE_SCHEDULE_ENABLED` / FE
  `compliance_schedule`, both **default off**. No new flag. With the flag off no
  compliance record can be written, so no code on this path can run; the Actions
  source-filter option is withheld for the same reason.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `pages/Actions.tsx` (source-type
  filter gains `compliance_record`, flag-gated; row link now passes
  `source_reference`), `pages/ActionDetail.tsx` (same link call),
  `components/investigations/handoffLinks.ts` (`getActionSourceLink` third
  optional argument + new `parseComplianceRequirementId`),
  `pages/actionsDisplayHelpers.ts` (`SOURCE_TYPE_LABELS.compliance_record`).
- **Backend (handlers/services):** `domain/services/capa_auto_service.py` (new
  `create_from_compliance_record`), `domain/services/compliance_schedule_service.py`
  (hook in `complete_requirement`, `capa_reference` on the audit payload),
  `api/routes/_action_unified.py` (`compliance_record` added to
  `CAPA_ONLY_API_SOURCE_TYPES`).
- **APIs (endpoints changed/added):** None added. `POST
  /api/v1/compliance-schedule/requirements/{id}/records` gains a side effect.
  `GET /api/v1/actions/?source_type=compliance_record` now resolves instead of
  returning an empty page.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** No response schema changed. The
  FE `SourceTypeFilter` union gains one member.
- **Database (migrations/entities/indexes):** **None.** `CAPASource.compliance_record`
  and the `capasource` enum label already landed in `20260913_cs_wave0`; this PR is
  the writer that revision anticipated. No new Alembic head.
- **Workflows/jobs/queues (if any):** None. The notification sweep is untouched.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive + Flagged.
- **Tolerant reader / strict writer applied?** Yes. `getActionSourceLink` takes
  `source_reference` as an *optional* third argument, so both existing call sites
  and any other caller keep working; a compliance action whose reference is
  absent or malformed resolves to **no link** rather than to
  `/compliance-schedule/{record id}`, which is a live route that would open a
  different obligation.
- **Breaking changes:** None.
- **Migration plan:** No migration. Existing compliance records are not
  backfilled — a CAPA is raised only for occurrences closed after this deploys.
- **Rollback strategy (DB):** No DB change. Reverting the commit stops new CAPAs;
  any already raised remain valid rows on the Actions register.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Completing an obligation with `check_passed=false` writes exactly
  one `capa_actions` row with `source_type=compliance_record`,
  `source_id={record id}`, `source_reference=compliance_requirement:{requirement id}`,
  `tenant_id` equal to the record's tenant, and priority CRITICAL/7 days for a
  statutory obligation or HIGH/30 days otherwise.
- [x] **AC-02:** `check_passed=true` and `check_passed=null` raise nothing —
  null means the obligation has no pass/fail dimension, not that it failed.
- [x] **AC-03:** A CAPA that cannot be raised fails the whole completion rather
  than committing a failed record with no remedy; the record and the rolled
  schedule are not written.
- [x] **AC-04:** Tenancy is derived from the record inside `CAPAAutoService` and
  cross-checked against the requirement; a mismatched tenant, a requirement the
  record does not belong to, an untenanted record, and an unflushed record are
  each refused before any row is added.
- [x] **AC-05:** Two concurrent failed completions of the same occurrence produce
  one record and one CAPA (201 + 409), never two of either.
- [x] **AC-06:** The Actions register lists the CAPA under
  `source_type=compliance_record`, labels it `Compliance record #{record id}`,
  never prints the `compliance_requirement:{id}` storage key, and links to
  `/compliance-schedule/{requirement id}`.

## 5) Testing Evidence (link to runs)
- [x] Lint — `eslint` clean on all changed FE files; `flake8` + `black --check`
  clean on all changed Python files.
- [x] Typecheck — `tsc --noEmit` clean; `mypy` clean on the changed services and
  the unified-actions helper.
- [x] Build — `tsc` gate above is the build's typecheck stage; full `vite build`
  left to CI.
- [x] Unit tests — new `tests/unit/test_compliance_schedule_capa.py` (16);
  `tests/unit` sweep on `-k "capa or action or compliance"` 674 passed, 3
  pre-existing skips.
- [x] Integration tests — `tests/integration/test_compliance_schedule_api.py` 21
  passed (5 new, exercising a real schema: `capa_actions.tenant_id` and
  `created_by_id` are NOT NULL and `source_type` is a database enum, none of
  which a mocked session can prove); `tests/integration -k "action or capa"` 65
  passed.
- [x] Contract tests (if applicable) — no contract changed; `i18n:check` green
  (4066 keys), and the one new key ships with an English fallback in the same
  style as its `actions.view_*` peers.
- [ ] E2E Smoke (critical journeys) — deferred to CI; the module is flag-off in
  every environment, so the smoke suite cannot reach this path.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Activate an obligation → close the occurrence with a failed
  check → a CAPA exists for that occurrence, on the right tenant, at the right
  priority. Covered end-to-end through the API in
  `test_a_failed_check_raises_one_capa_for_the_completing_tenant`.
- [x] **CUJ-02:** Open Actions → filter to Compliance schedule → the raised CAPA
  is listed with an honest source label and follows its link back to the
  obligation. Covered by
  `test_the_raised_capa_is_reachable_from_the_actions_register` and
  `Actions.complianceSource.test.tsx`.
- [x] **CUJ-03:** Close an occurrence that passed → nothing lands on the Actions
  board.

## 7) Observability & Ops
- **Logs:** `capa_auto_service` logs one INFO per raised CAPA with the record
  reference, requirement reference and tenant id — enough to reconcile a CAPA
  against its occurrence without opening the database.
- **Metrics:** None added. Volume is observable as
  `capa_actions.source_type = 'compliance_record'`.
- **Alerts:** None added. A CAPA that cannot be raised surfaces as a 5xx on the
  completion endpoint, which existing API error-rate monitoring already sees;
  that is deliberate and is the point of AC-03.
- **Runbook updates:** none required — `docs/runbooks/COMPLIANCE_SCHEDULE_ROLLOUT.md`
  is unchanged, as the enable steps and permissions are unchanged.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** with `COMPLIANCE_SCHEDULE_ENABLED=true` and
  `compliance_schedule:update` granted, complete an obligation with the check
  marked failed; confirm a `CAPA-` reference appears under Actions → Compliance
  schedule, that the row's source reads `Compliance record #N`, and that its link
  lands on the obligation.
- **Canary plan:** not used. The module is flag-off in production, so the
  behaviour reaches no production traffic on merge; the flag flip is the real
  exposure event and is a separate, explicitly requested step.
- **Prod post-deploy checks:** confirm the ACA image tag matches the tip SHA and
  the prod FQDN is healthy. No compliance-schedule check applies while the flag
  is off.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** failed completions returning 5xx, duplicate CAPAs for one
  occurrence, or any CAPA appearing under the wrong tenant.
- **Rollback steps:** revert this commit on `main` and let the pipeline deploy the
  reverted state; no migration to unwind and no data to repair. Faster mitigation
  without a deploy: set `COMPLIANCE_SCHEDULE_ENABLED=false` (or engage the
  `compliance_schedule` kill switch), which closes the only endpoint that can
  reach this code. Already-raised CAPAs are ordinary rows and stay on the
  register.
- **Owner:** David Harris.

## 10) Evidence Pack (links)
- CI run(s): to be linked from the Checks tab of this PR at its tip SHA.
- Staging deploy evidence: to follow the merge; see §8 for what to capture.
- Canary evidence (if applicable): n/a — no canary, see §8.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — no response
  contract changed; the FE helper change is additive and backwards-compatible.
- [ ] **Gate 2:** CI green (lint/type/build/tests) — local gates green, awaiting CI
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — not used, see §8
- [x] **Gate 5:** Production verification plan + monitoring ready — see §7 and §8

## Residual risk (honesty)
- `requirement.owner_id` is validated as in-tenant when it is **written**
  (`_assert_owner_in_tenant`), not when it is read here. A user moved between
  tenants after assignment would leave a stale assignee on a new CAPA. The row's
  own `tenant_id` is what every Actions query filters on, so this cannot expose
  the CAPA across tenants — it would only mis-attribute ownership.
- `capa_actions.reference_number` is globally unique while
  `ReferenceNumberService` derives the next sequence with MAX/COUNT under RLS,
  which sees only the current tenant's rows. A cross-tenant collision is
  therefore possible and, on this path, would take the completion down with it.
  Pre-existing for every CAPA writer (incident, audit finding, assessment); the
  fix belongs in the reference-number service and is deliberately not attempted
  here.
- The missed-occurrence sweep writes `outcome=missed` with no `check_passed`, so
  a missed obligation still raises nothing. Whether a missed statutory obligation
  should owe a CAPA is a product decision, not an oversight.
- The compliance detail page does not surface the CAPA it raised; the operator
  finds it on the Actions register. Adding it needs a `RecordResponse` field and
  was left outside this PR's fence.
