# Change Ledger (CL-ADR-0022-JOB-AXIS)

## 1) Summary
- **Feature / Change name:** ADR-0022 — Job Lifecycle axis vocabulary (no second org SSOT)
- **User goal (1–2 lines):** Lock before JL-1 whether job type / lane / step bind to LookupOption, free-text department, or a new org entity — and refuse a second organisation system of record.
- **In scope:** `docs/adr/ADR-0022-job-axis-vocabulary.md`; this Change Ledger
- **Out of scope:** JL schema/API/UI; migrations; LookupOption seed changes; rewriting module `department` columns; enabling `job_lifecycle`
- **Feature flag / kill switch:** N/A (docs-only). Programme flags `job_lifecycle` / `job_cell_links` remain default **off** (already pre-registered)

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** None (docs-only)
- **Docs:** New ADR-0022 accepted decision record

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Documentation only; no runtime behaviour change
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert commit / supersede ADR status if product reverses

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| JL axis vs org vocabulary | Unlocked — risk of second org SSOT in JL-1 | ADR-0022: axes are JL process vocab; no new Department/OrgUnit entity |
| LookupOption as lane/step identity | Possible accidental binding | Rejected — lookups may annotate only, never identify axes |
| Free-text department as axis identity | Possible accidental binding | Rejected — free-text remains module display/filter; not JL identity |
| Document SSOT inside job cells | Belt non-goal stated | Reinforced: cells hold `library_document_id[]` only |
| Existing module `department` fields | Free-text across modules | Unchanged — no migration in this programme |

## 4) Acceptance Criteria (AC)
- [x] AC-01: ADR-0022 exists under `docs/adr/` with Accepted status
- [x] AC-02: Decision rejects new org-unit entity for this programme
- [x] AC-03: Decision rejects LookupOption and free-text department as axis **identity**
- [x] AC-04: Decision allows optional nullable department **annotation** later without reopening axis identity
- [x] AC-05: Diff touches `docs/adr` (+ this ledger) only — no app/migration/FE files

## 5) Testing Evidence (link to runs)
- [ ] Lint / markdown — CI as applicable
- [x] Diff review — docs/adr + Change Ledger only
- [ ] Unit / Integration / Contract / E2E — N/A docs-only

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Reader can answer “what are lanes/steps?” → JL process axes, not departments
- [x] CUJ-02: Reader can answer “do we build OrgUnit?” → No, not this programme
- [x] CUJ-03: JL-1 implementer knows cells reference library document IDs only

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None
- **Runbook updates:** None — gate note: JL-1 stays blocked until X-2 is PROD LIVE **and** this ADR is merged

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Docs ship with tip; no flag flips; no behavioural bake
- **Canary plan:** N/A

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Product reverses and wants LookupOption-as-axis or a new org entity before JL-1
- **Rollback steps:** Supersede ADR-0022 with a follow-on ADR (do not silently contradict); revert this commit if the file must leave `main`
- **Owner:** Platform Engineering (Job Lifecycle) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: N/A docs-only (tip chase follows normal main deploy)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (vocabulary lock only; no API this PR)
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A docs-only pre-merge
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA after merge; no flag enablement
