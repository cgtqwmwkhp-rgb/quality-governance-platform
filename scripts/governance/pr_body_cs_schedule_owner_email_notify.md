# Change Ledger (CL-CS-SCHEDULE-OWNER-EMAIL-NOTIFY)

## 1) Summary
- **Feature / Change name:** Compliance Schedule — owner assignment email/notify + due-reminder email + admin toggles
- **User goal (1–2 lines):** When someone is allocated as schedule owner they get notified (in-app + email when allowed); due reminders can email as well; admins can turn these on/off without a migration.
- **In scope:** Pure builders + best-effort assignment notify hooked in `ComplianceScheduleService`; sweep email enqueue; three feature flags seeded via Feature Flags API; Admin Notification Settings wired to those flags; runbook honesty (08:15 schedule + occurrence roll-forward stops reminders).
- **Out of scope:** `src/api/routes/compliance.py` / WI-1 CEL; `compliance_schedule.py` route edits (owner display PR); alembic; inventing cancel jobs for reminders.
- **Feature flag / kill switch:** Module opener + `compliance_schedule_kill_switch` still close everything. New flags (default on): `compliance_schedule_assignment_notify`, `compliance_schedule_due_reminder_notify`, `compliance_schedule_email_enabled`.

## 2) Impact Map (what changed)
- **Frontend:** `NotificationSettings.tsx` — real CS toggles via `GET/PATCH /api/v1/feature-flags/`; cosmetic channel cards labelled as non-persistent.
- **Backend:** `compliance_schedule_notifications.py` (assignment builders); `compliance_schedule_notify_flags.py` (seed/evaluate); `compliance_schedule_assignment_notify.py`; hooks in `ComplianceScheduleService`; sweep email enqueue + counters; list feature-flags ensures seed.
- **APIs:** Feature flags list seeds CS notify rows (no new endpoints).
- **Schemas/contracts:** None.
- **Database:** None (no alembic).
- **Workflows/jobs/queues:** Existing daily 08:15 sweep may enqueue `send_email` on the `email` queue after new COMPLIANCE_ALERT rows.
- **Config/env/flags:** Three `feature_flags` rows (seeded, no migration).
- **Dependencies:** None.
- **Tests:** Assignment builder/notify unit tests; due-reminder email enqueue + flag-off; sweep registration counters.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive notify paths; missing flag rows default **on** until seeded.
- **Tolerant reader / strict writer applied?** Yes.
- **Breaking changes:** None.
- **Migration plan:** N/A — no alembic.
- **Rollback strategy (DB):** No DB schema change — disable flags or revert deploy.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Owner allocation awareness | In-app due sweep only; no assignment notify | New owner notified on create/activate/import/owner change (best-effort) |
| Due reminder email | In-app COMPLIANCE_ALERT only | Optional email enqueue after successful insert when flags/prefs allow |
| Admin control of CS notify | Kill switch / module opener only | Per-channel feature flags + Admin Notification Settings (persisted) |
| Reminder stop after complete | `next_due_date` roll-forward + dedupe key | Unchanged; documented (no cancel job) |
| WI-1 CEL / `compliance.py` | Untouched | Still untouched |
| Schedule routes (`compliance_schedule.py`) | Owned by #1688 | Untouched in this PR |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Owner allocation (create / activate / import path / update when `owner_id` changes) notifies the **new** owner; no notify when owner unchanged or unassigned.
- [x] AC-02: Due sweep can enqueue email after successful COMPLIANCE_ALERT insert; respects email flag + `NotificationPreference.email_enabled`.
- [x] AC-03: Flags `compliance_schedule_assignment_notify`, `compliance_schedule_due_reminder_notify`, `compliance_schedule_email_enabled` seeded/toggleable; flag off → no send for that path.
- [x] AC-04: Notify failures never fail the requirement save (best-effort).
- [x] AC-05: Runbook documents 08:15 schedule and that completing a cycle stops reminders via next_due roll-forward.
- [x] AC-06: No alembic; no edits to `compliance.py` or `compliance_schedule.py` routes.

## 5) Testing Evidence
- [x] `python3.11 -m pytest tests/unit/test_compliance_schedule_notifications.py tests/unit/test_compliance_schedule_assignment_notify.py tests/unit/test_compliance_schedule_due_reminder_email.py tests/unit/test_compliance_schedule_sweep_registration.py -q` — 54 passed
- [ ] Full CI on PR

## 6) Critical Journeys
- [x] CUJ-01: Allocate owner on create/activate → new owner gets ASSIGNMENT notify (email if flags/prefs/SMTP allow).
- [x] CUJ-02: Change owner on update → new owner notified once; same-owner PATCH does not re-notify.
- [x] CUJ-03: Due sweep creates COMPLIANCE_ALERT → email enqueued when flags on; flag off → no send; completing occurrence advances next_due so reminders stop for that cycle.

## 7) Observability & Ops
- Sweep result adds `emails_enqueued` / `emails_skipped`.
- Assignment failures log `compliance_schedule_assignment_notification_failed` without raising.
- Runbook: `docs/runbooks/COMPLIANCE_SCHEDULE_SWEEP_OPS.md` updated.

## 8) Release Plan
1. Merge after CI green (do not tip-chase from this PR authoring step).
2. Main CI → Azure deploy → verify ACA tip SHA + health.
3. Confirm flags present via Admin → Notification Settings or `GET /api/v1/feature-flags/`.
4. Spot-check: assign schedule owner → in-app (+ email if SMTP live); dry-run sweep before trusting first email backlog.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Notify/email spam, wrong recipients, or admin toggle not persisting.
- **Rollback steps:** Set the three CS notify flags `enabled=false` (seconds); or engage kill switch; or revert merge commit and redeploy. No DB unwind.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack
- Unit: assignment + due-reminder email + builders + sweep registration
- Change Ledger: this body

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive notify + flags (no schema migration)
- [ ] **Gate 2:** CI green on the PR
- [ ] **Gate 3:** Staging verification (after merge/deploy)
- [x] **Gate 4:** Canary N/A — notify/email + admin toggles
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed at open
