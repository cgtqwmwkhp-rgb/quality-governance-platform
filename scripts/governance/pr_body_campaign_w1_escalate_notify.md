# Change Ledger (CL-CAMP-W1-ESCALATE-NOTIFY)

## Summary
Wave 1 backend for document campaigns: **O-03** overdue escalation notifications (assignee + optional manager + HSEC owner) and **O-05** typed campaign notifications via distinct `entity_type` values without PostgreSQL enum migration (Option B).

## Allowlist (exclusive)
| File | Change |
|------|--------|
| `src/domain/services/document_campaign_notifications.py` | NEW — typed notification builders + recipient helpers |
| `src/domain/services/document_campaign_service.py` | `process_due_reminders`, typed launch notify |
| `src/infrastructure/tasks/document_campaign_tasks.py` | NEW — Celery beat sweep |
| `src/infrastructure/tasks/celery_app.py` | Register task module + daily beat entry |
| `tests/unit/test_document_campaign_overdue_notifications.py` | NEW — overdue + typed notify unit proof |
| `scripts/governance/pr_body_campaign_w1_escalate_notify.md` | This Change Ledger |

## O-05 design choice
**Option B chosen.** `NotificationType` is backed by a PostgreSQL enum (`notificationtype`) created in `20260220_add_notification_tables.py`; adding `CAMPAIGN_*` values would require an Alembic `ALTER TYPE` migration. Instead we reuse existing types and distinguish campaigns by `entity_type`:
| Scenario | `NotificationType` | `entity_type` | Title |
|----------|-------------------|---------------|-------|
| Launch assign | `assignment` | `document_campaign` | Document campaign assigned |
| Reminder | `action_due_soon` | `document_campaign_reminder` | Document campaign reminder |
| Overdue | `action_overdue` | `document_campaign_overdue` | Role-specific overdue title |

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Campaign launch notify | Generic assignment row | Typed `document_campaign` entity + distinct title |
| Reminder sweep | Not implemented | Daily Celery task sends reminders + escalates overdue |
| Overdue PENDING assignments | Stay pending | Marked OVERDUE + notify assignee/manager/HSEC |

## Compatibility
- Additive only; no API schema changes.
- Manager notify skipped when `User` has no `manager_id` / `supervisor_id` / `reports_to` (current model has none).
- Notification failures are best-effort; reminder job always commits status transitions.

## Acceptance criteria
- **AC-01**: PENDING assignment past `due_at` transitions to OVERDUE during reminder sweep.
- **AC-02**: Overdue escalation creates in-app notifications for assignee and HSEC owner (`created_by_id` / `launched_by_id`).
- **AC-03**: Manager notified when User exposes `manager_id`, `supervisor_id`, or `reports_to`.
- **AC-04**: Launch + reminder notifications use distinct `entity_type` values (`document_campaign`, `document_campaign_reminder`, `document_campaign_overdue`).
- **AC-05**: Notification insert failures do not abort the Celery reminder sweep.
- **AC-06**: Unit tests prove overdue escalation creates typed notifications.

## Testing evidence
- `pytest tests/unit/test_document_campaign_overdue_notifications.py -q`
- `pytest tests/unit/test_document_campaign_service.py -q` (regression)

## Critical journeys
- **CUJ-01**: Active campaign assignment passes due date → assignee receives overdue notification with `document_campaign_overdue` entity type.
- **CUJ-02**: Daily reminder sweep fires pre-due reminder with `document_campaign_reminder` entity type without marking assignment overdue.

## Observability
- Celery task logs sweep counters: `assignments_scanned`, `reminders_sent`, `overdue_escalated`, `notifications_created`.
- Per-notification failures logged at warning without failing the job.

## Release plan
1. Merge after CI green (do not auto-merge).
2. Deploy backend + Celery worker/beat; confirm beat entry `process-document-campaign-reminders` registered.
3. Staging: launch campaign, backdate assignment `due_at`, run task manually; verify notifications.

## Rollback plan
1. Revert squash commit on main.
2. Redeploy previous SHA.
3. Remove beat entry if worker still schedules the task.

## Evidence pack
- CI run links attached after push
- Staging overdue notification screenshot: pending Gate 3

## Gate checklist
- [x] Gate 0 — change ledger + exclusive allowlist
- [x] Gate 1 — scope limited to campaign notify/reminder lane
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack

## Test plan
- [ ] `pytest tests/unit/test_document_campaign_overdue_notifications.py -q`
- [ ] `pytest tests/unit/test_document_campaign_service.py -q`
- [ ] Manual: trigger `process_document_campaign_reminders` on staging with overdue assignment
