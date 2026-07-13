# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Remove PagerDuty deliverable and Events API path
- **User goal (1–2 lines):** Permanently descope PagerDuty (EA-05 Cancelled); delete app-level Events API integration; keep SMTP + Azure Monitor email as ops alerting.
- **In scope:** Delete PD client/status/tasks/tests; unwind `/readyz` and DLQ paging; rename SMTP wire script; cancel EA-05; update alerting/runbooks
- **Out of scope:** Assessor #922; changing Azure Monitor alert rules; mass-rewriting historical scorecards
- **Feature flag / kill switch:** N/A — removal

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** health/readyz, main root readyz, DLQ, celery includes, alerting package emptied of PD
- **APIs:** `/readyz` no longer exposes `pagerduty` / `pagerduty_configured`
- **Database:** None
- **Workflows/jobs:** Removed `pagerduty_tasks`; DLQ no longer pages PD
- **Config/env:** `PAGERDUTY_*` no longer used
- **Docs:** EA-05 Cancelled; HUMAN_UNLOCK_SMTP; alerting-integration; ops light touch

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Breaking for clients that parsed `checks.pagerduty` — intentional product removal
- **Breaking changes:** `/readyz` loses pagerduty fields
- **Migration plan:** None
- **Rollback strategy:** Revert PR if needed

## 4) Acceptance Criteria (AC)
- [x] AC-01: No PagerDuty modules under src/infrastructure/alerting or tasks
- [x] AC-02: `/readyz` has no pagerduty object (root + API health)
- [x] AC-03: EA-05 Cancelled in external-attestation-tracker
- [x] AC-04: wire_smtp.sh exists; wire_smtp_pagerduty.sh removed
- [x] AC-05: Integration health tests updated

## 5) Testing Evidence
- [ ] Unit / integration CI on PR
- [x] Local: PD modules deleted; health tests no longer import PD

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Readiness returns without pagerduty keys
- [x] CUJ-02: SMTP wire path documented without PD
- [x] CUJ-03: EA-05 Cancelled visible in attestation tracker

## 7) Observability & Ops
- **Logs:** DLQ critical no longer enqueues PD
- **Alerts:** Azure Monitor email action groups remain SSOT
- **Runbook updates:** HUMAN_UNLOCK_SMTP.md; alerting-integration.md

## 8) Release Plan
- Staging then prod via normal conveyor; confirm `/readyz` has no pagerduty after promote

## 9) Rollback Plan
- Revert squash merge and redeploy previous SHA

## 10) Evidence Pack
- CI: this PR
- Staging/prod: post-deploy curl `/readyz` — assert no `pagerduty`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts (readyz field removal intentional)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** N/A
- [x] **Gate 5:** Prod verification plan
