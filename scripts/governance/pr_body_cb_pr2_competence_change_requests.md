# Change Ledger (CL-CB-PR2-COMPETENCE-CHANGE-REQUESTS)

## 1) Summary
- **Feature / Change name:** CB-PR2 — competence change requests (plant → IT-Admin, statutory → HR Advisor)
- **User goal:** Ask the source-system owner to issue or revoke a skill without QGP writing PAMS or Citation. The row is the request; email is best-effort; the request closes when the snapshot/import matches.
- **In scope:** `competence_change_requests` table; `POST/GET /api/v1/workforce/competence/change-requests` behind the existing closed flag; mailbox routing; one open request per cell; auto-close plant requests after a successful PAMS snapshot
- **Out of scope:** Live CompetencyDashboard; GET board `family=atlas` (CB-PR3); assessment overlay (CB-PR4); schedule quorum (CB-PR5); flag-on (CB-PR6); PAMS writes; mark-applied; bulk Users; Entra
- **Feature flag / kill switch:** Same `COMPETENCE_BOARD_ENABLED` / `FF_COMPETENCE_BOARD` default false. Kill = flag off. Kill SHA = previous LIVE `1fa285926146`.

## 2) Impact Map (what changed)
- **Frontend:** none. CompetencyDashboard unchanged.
- **Backend:** change-request model/service, board routes, snapshot auto-close hook, mailbox settings
- **APIs:** Additive `POST`/`GET /api/v1/workforce/competence/change-requests` — 404 while flag closed; `engineer:update` when open. `GET .../board?family=atlas` remains 422.
- **Database / flags:** Additive `competence_change_requests`. No backfill.
- **Workflows/jobs:** Existing hourly PAMS competence beat now auto-closes matching plant requests.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive table and closed-flag routes.
- **Breaking changes:** None
- **Migration plan:** Additive. Partial unique index: one open row per tenant/family/engineer/characteristic.
- **Rollback strategy (DB):** Flag off. Table may remain unused.

## Compliance Delta
- **ISO 9001 7.2 / ISO 45001 7.2:** Issued plant competence stays in PAMS; statutory stays in Atlas/Citation. QGP records the request and observes the source.
- **What this PR does not claim:** Live board UI, demonstrated overlay, or coverage quorum.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag default false. Change-request routes 404 when closed.
- [x] AC-02: Plant requests route to `IT-Admin@plantexpand.com` (overridable). Statutory requests require `COMPETENCE_STATUTORY_CHANGE_MAILBOX` / `HR_ADVISOR_MAILBOX`.
- [x] AC-03: QGP never writes PAMS. No mark-applied endpoint.
- [x] AC-04: One open request per cell. Same action returns the existing row; conflicting action is 409.
- [x] AC-05: SMTP failure leaves the row. Email is best-effort after the row exists.
- [x] AC-06: A later PAMS snapshot that matches issue/revoke closes the plant request with `source_observed`.
- [x] AC-07: `GET /board?family=atlas` stays 422 (CB-PR3).
- [x] AC-08: CompetencyDashboard unchanged.

## 5) Testing Evidence (link to runs)
- [ ] Unit — `tests/unit/test_competence_change_requests.py`
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag off → change-requests 404
- [x] CUJ-02: Plant mailbox is IT-Admin; unset HR mailbox is an honest error, not a silent drop
- [x] CUJ-03: Issue closes when the snapshot has the cell; revoke closes when it does not

## 7) Observability & Ops
- **Logs:** `competence_change_request email skipped` without tokens
- **Runbook:** Leave flag false. Set `HR_ADVISOR_MAILBOX` in Azure before exercising statutory requests.

## 8) Release Plan
- **Staging:** Flag stays false. Confirm 404 on change-requests.
- **Prod post-deploy:** healthz; `build_sha` == tip; flag false; Entra stays false

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any PAMS write, mark-applied endpoint, or CompetencyDashboard change
- **Rollback steps:** Revert squash on `main` and redeploy previous LIVE SHA `1fa285926146`
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (closed flag; additive requests; live page untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Production verification plan + monitoring ready
