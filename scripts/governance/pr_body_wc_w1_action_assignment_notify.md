# Change Ledger — D-W1-11 Action assignment notify all sources

## Summary
Closes D-W1-11 residual: prove and harden assignee notify + audit for the **unified action fabric** (`POST/PATCH /api/v1/actions`) across all source types. #935 delivered the live notify hooks; this lane extracts a testable service, adds explicit `unified_action.assigned` audit events, and unit proof so regressions are caught without re-touching portal triage or legacy nested routes.

## What was already LIVE (#932 / #935)
| Surface | Status |
|---------|--------|
| #932 Actions My Work filters | **Not notify scope** — `assigned_to=me` / `overdue` query filters only |
| #935 `POST /api/v1/actions` with `assigned_to_email` | `NotificationService.create_assignment` + 400 on unknown email |
| #935 `PATCH /api/v1/actions` reassign | Notify when `assigned_to_email` changes to a new user |
| #935 incident/complaint case owner PATCH | Assignment notify on **case** owner (not action fabric) |
| #935 integration CUJ | `tests/integration/test_ops_intake_triage_cuj.py` proves incident action create notify |
| Unified sources on create/update | incident, rta, complaint, investigation, assessment, induction, audit_finding (CAPA rows) |
| Generic audit on create/update | `unified_action.created` / `unified_action.updated` |

## What this PR adds
| File | Change |
|------|--------|
| `src/domain/services/action_assignment_service.py` | NEW — `notify_action_assignment` + `record_action_assigned_audit` |
| `src/api/routes/actions.py` | Wire service; `assigned_to_user_id` on create payload; `unified_action.assigned` on create-with-assignee and reassign |
| `tests/unit/test_action_assignment_notify.py` | NEW — notify + audit unit proof |
| `scripts/governance/pr_body_wc_w1_action_assignment_notify.md` | This ledger |

## Impact map
| Surface | Before (#935) | After |
|---------|---------------|-------|
| Unified `POST /api/v1/actions` | Inline notify + generic audit | Extracted service + `unified_action.assigned` audit |
| Unified `PATCH` reassign | Inline notify on email change | Service helper + explicit assigned audit |
| Regression safety | Integration CUJ only | Unit proof for notify + audit helpers |

## Out of scope (honesty)
- **Legacy nested routes** without notify: `POST/PATCH /rtas/{id}/actions`, `/api/v1/capa`, vehicle checklist defect actions, Planet Mark improvement actions — not in exclusive allowlist; unified fabric is the platform contract for My Work.
- **Portal auto-triage** (#970 lane) — separate D-W1-08 work.
- **SMTP** — in-app notify only (#853 parked).

## Acceptance criteria
- **AC-01**: Assignee receives in-app assignment notification on unified action create (all source types) when `assigned_to_email` resolves.
- **AC-02**: Assignee receives notification on unified action reassign (`PATCH` with new `assigned_to_email`).
- **AC-03**: `unified_action.assigned` audit event recorded on create-with-assignee and on reassign.
- **AC-04**: `unified_action.created` payload includes `assigned_to_user_id` when assignee present.
- **AC-05**: Unknown `assigned_to_email` still returns 400 (unchanged #935 behaviour).
- **AC-06**: Unit tests prove notify + audit helpers.

## Testing evidence
- `pytest tests/unit/test_action_assignment_notify.py`
- Existing: `tests/integration/test_ops_intake_triage_cuj.py` (incident action create notify)

## Critical journeys
- **CUJ-01**: Create unified action from any source with assignee → in-app notify + `unified_action.assigned` audit
- **CUJ-02**: Reassign unified action via PATCH with new `assigned_to_email` → new assignee notified + assigned audit

## Compatibility
- Additive audit events and payload fields only.
- Notify failures logged; committed assign is not rolled back (same as #935).

## Observability
- `unified_action.assigned` audit events on create-with-assignee and reassign
- Notify failures logged at exception without rolling back committed assign

## Release plan
1. Update branch from main, then squash-merge after CI green
2. Staging: create + reassign unified action; confirm notification + audit trail
3. Production deploy with full release SHA

## Rollback plan
1. Revert squash commit on main
2. Redeploy previous SHA
3. Unified actions revert to #935 inline notify (no `unified_action.assigned` audit)

## Evidence pack
- CI run links attached after push
- Staging notify + audit screenshot: pending Gate 3

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — exclusive allowlist only
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack

## Test plan
- [ ] `pytest tests/unit/test_action_assignment_notify.py -q`
- [ ] `pytest tests/integration/test_ops_intake_triage_cuj.py -q` (regression)
- [ ] Manual: create + reassign unified action; confirm notification row + `unified_action.assigned` in audit trail
