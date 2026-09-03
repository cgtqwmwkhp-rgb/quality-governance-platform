# Change Ledger (CL-CB-UI-4-COVERAGE-DUES)

> Adjacent, not fixed here: Atlas still has no Location foreign key. `match_department` remains an
> operator-typed exact string. A quota with no department stays `unknown` and is not due-pulled.
>
> Also adjacent: FE / contract roles stay off `COVERAGE_ROLE_KEYS` until Citation course labels are
> named. Identity honesty (engineer / Atlas person / Azure user) is CB-UI-5.

## 1) Summary
- **Feature / Change name:** CB-UI-4 — coverage shortfall dues the location occurrence; 30-day Atlas expiry forecast on the People tab
- **User goal:** When a site drops below n-of-m appointed cover, the location duty on the compliance schedule becomes due. Thirty days before an expiry would break the quorum, the People tab names who will drop the site below n. Names stay on Atlas; the duty stays on the schedule.
- **In scope:** Write-path due-pull of `ComplianceRequirement.next_due_date` to today on a matched shortfall (Atlas import persist + quota save); additive `forecast` on `GET /coverage`; People-tab panel listing those Atlas names
- **Out of scope:** FE/contract roles; CB-UI-5 identity honesty; bulk Users; Entra; fuzzy department/location join; person-scoped schedule rows; auto-complete when cover recovers; PAMS writes; completing AUD-2026-0087; ISO 14001 S0; Voyage V0
- **Feature flag / kill switch:** `COMPETENCE_BOARD_ENABLED` already default true (CB-PR6). Delete the quota to stop further due-pulls; existing dates stay until the operator completes the occurrence. Overlay GET is unchanged and still does not move `next_due_date`. Kill SHA = previous LIVE `c2150dfb3c9e`.

## 2) Impact Map (what changed)
- **Frontend:** People tab on Workforce → Competency calls `GET /coverage` and lists a 30-day dropout forecast. Plant tab does not. Coverage 404 leaves the Atlas board in place and invents no zeros.
- **Backend:** `assemble_coverage_forecast`; `apply_coverage_shortfall_dues_async` (flush-only, audited). Hooked from Atlas import persist and `POST /coverage-quotas`. Schedule GET overlay is still read-only.
- **APIs:** `CompetenceCoverageResponse.forecast` additive list (default empty). Item payloads still carry no person fields.
- **Database / flags:** none. No migration. `next_due_date` on an existing location requirement may move to today.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive forecast field. Clients that ignore unknown keys keep working. Due-pull is a write on a known column, only when `gap` is true and the quota is not unknown, and only when `next_due_date` is still in the future.
- **Breaking changes:** none.
- **Migration plan:** none.
- **Rollback strategy (DB):** Revert the squash. Dates already pulled to today stay until an operator completes the occurrence (same as any due date). Flag off 404s `/coverage` and the People panel degrades; it does not un-due a date.
- **Write-path safety:** Never inside schedule GET. Unknown quotas do not due. Recovered cover does not auto-complete. No `ComplianceRecord` is created. No person-scoped requirement. QGP never writes PAMS.

## Compliance Delta
- **ISO 45001 7.2 (competence):** the organisation determines the competence needed (quorum), retains Atlas as evidence of who holds it, and takes action to acquire cover — the location occurrence becomes due so it appears on the schedule the operator already uses.
- **Health and Safety (First-Aid) Regulations 1981 / Fire Safety Order 2005:** still a premises duty. Named people stay on Atlas.
- **ADR-0020:** the requirement still holds the schedule; records are still occurrences. Status still derives from `next_due_date` alone — that is why the date must move. This does not pre-create a record and does not add a person-scoped row.
- **What this PR does not claim:** that cover has been restored; that QGP wrote PAMS or Citation; that an Atlas department is a location; that FE/contract roles exist.

## 4) Acceptance Criteria (AC)
- [x] AC-01: When a matched quota is short (`gap` true, not unknown), `apply_coverage_shortfall_dues_async` sets the matching location requirement's `next_due_date` to today if it was in the future. No new `ComplianceRequirement` row. Audit event `compliance_schedule.coverage_shortfall_due`.
- [x] AC-02: Unknown quotas (no import, or `match_department` null) do not due. Already-overdue dates are kept. Restored cover does not roll the date forward.
- [x] AC-03: Schedule overlay GET still does not move `next_due_date` (CB-PR5 read path held).
- [x] AC-04: 30-day forecast lists Atlas people whose expiry, in date order, takes a currently-met site below n. An expiry that leaves the site at n is omitted. Already-short and unknown quotas are omitted.
- [x] AC-05: `GET /coverage` returns `forecast` with Atlas names. Coverage item payloads still have no `people` / `engineer_id` fields. `COVERAGE_ROLE_KEYS` remains first_aider, fire_marshal, mhfa.
- [x] AC-06: People tab shows the forecast; Plant tab does not fetch coverage. Coverage 404 does not hide the Atlas board and invents no forecast zeros. QGP creates no User.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_competence_coverage_dues.py` + `tests/unit/test_competence_coverage_quorum.py`: 48 passed.
- [x] Frontend — `npx vitest run src/pages/workforce/__tests__/CompetenceBoard.test.tsx`: 26 passed.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Two appointed first aiders required, one in date. Import/due-pull moves the location duty to today. No person-scoped row appears.
- [x] CUJ-02: Three first aiders, n=2; Pat expires in 10 days, Sam in 18, Lee next year. Forecast names Sam (the expiry that drops the site below n), not Pat.
- [x] CUJ-03: Operator completes the location occurrence after Citation is current. This slice does not auto-complete.
- [x] CUJ-04: People tab 404 on `/coverage` still shows Atlas rows. No FE/contract role is offered.

## 7) Observability & Ops
- **Logs:** `compliance_schedule.coverage_shortfall_due` with previous and new dates, quota id, current_m, required_n.
- **Runbook:** Due-pull runs after a successful Atlas import and after saving a quota. To stop further pulls, delete the quota. To clear a due, complete the location occurrence when cover is restored — do not expect the next import to roll the date forward.

## 8) Release Plan
- **Staging:** Confirm `/healthz`. Confirm People tab loads `/coverage`. Confirm a sandbox shortfall moves `next_due_date` on the matching location duty only.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip; Entra attestation flag stays false. QGP never writes PAMS.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a person-scoped compliance-schedule row; a PAMS or Citation write; due-pull of an unknown quota; schedule GET mutating dates.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `c2150dfb3c9e`. Dates already pulled remain until operator complete.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (forecast additive; due-pull write-path only; ADR-0020 held; no FE roles; no Users; no PAMS write)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — behaviour is additive on existing flag-on board)
- [x] **Gate 5:** Production verification plan + monitoring ready
