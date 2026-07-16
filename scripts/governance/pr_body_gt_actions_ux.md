# Change Ledger (CL-GT-ACTIONS-UX)

## Summary

- **Change:** harden the Actions UX golden-thread residuals R23, R26, and R30; retain R29 as a production-evidence waiver candidate.
- **User outcome:** assignments remain durable when notification delivery fails, Actions/CAPA writes are safely retried, and verified actions are not presented as overdue.
- **Scope:** the listed backend notification service, Axios client, Actions fallback rendering, focused tests, and this ledger only.

## Impact Map

| Flag | Disposition | Impact |
|---|---|---|
| R26 | Fixed | Assignment-notification failures remain non-fatal and emit a structured warning with action, assigner, assignee, and exception type. |
| R30 | Fixed | The primary Axios client adds `Idempotency-Key` to Actions/CAPA `POST`/`PUT`/`PATCH` writes; an auth-refresh retry retains the original key. |
| R29 | Waive candidate | The live D20 client route returns `200 {linked:false}` for unlinked users. Waive only with deployed-version evidence; remaining 404s are outside this client path. |
| R23 | Fixed | Fallback overdue rendering treats `verified` as terminal, matching the server terminal-action filter. |

## Compatibility

- No migrations, route changes, or API response-contract changes.
- Existing caller-provided idempotency keys are preserved.
- Only Actions/CAPA write paths receive the new request header; other API traffic is unchanged.

## Acceptance Criteria

- [x] AC-01: assignment notification delivery failures are observable without rolling back a committed assignment.
- [x] AC-02: Actions/CAPA `POST`/`PUT`/`PATCH` writes carry a stable per-request `Idempotency-Key`.
- [x] AC-03: an auth-refresh retry preserves the original idempotency key.
- [x] AC-04: verified, past-due actions are not shown as overdue in the fallback view.

## Testing Evidence

- [x] `pytest tests/unit/test_action_assignment_notify.py -q` — 5 passed.
- [x] `npx vitest run src/api/client.test.ts src/pages/__tests__/Actions.test.tsx` — 24 passed, 1 skipped.
- [x] `npm run lint` — passed with zero warnings.
- [ ] Required CI checks green after push.

## Critical Journeys

- [x] CUJ-01: assign an action while notification delivery fails; the assignment commits and structured warning context is logged.
- [x] CUJ-02: submit an Actions/CAPA write, receive a 401, refresh authentication, and retry with the same idempotency key.
- [x] CUJ-03: view a verified action whose due date has passed; it is not labelled overdue.

## Observability

- `action_assignment_notification_failed` warning includes `action_id`, `assigned_to_user_id`, `assigned_by_user_id`, and `exception_type`, with exception trace.
- Monitor the structured warning rate after deployment; investigate sustained increases by action and assignee.

## Release Plan

1. Merge only after required CI and the focused frontend checks pass.
2. Deploy the merged tip and verify one Actions/CAPA write includes `Idempotency-Key`.
3. Verify a notification-failure warning is searchable and re-run the verified-action display journey.
4. Attach deployed-version evidence before accepting the R29 waiver.

## Rollback Plan

- **Owner:** On-call application engineer / release manager.
- **Rollback steps:** revert the squash-merge commit, deploy the revert, and verify normal Actions assignment and write flows.
- **Decision trigger:** elevated client write failures, unexpected duplicate behavior, or material notification-warning regression.

## Evidence Pack

- Focused backend test output: `tests/unit/test_action_assignment_notify.py` (5 passed).
- Focused frontend tests: `frontend/src/api/client.test.ts` and `frontend/src/pages/__tests__/Actions.test.tsx`.
- Deployment request trace showing the write idempotency header and structured-log sample for R26.
- Production route/version evidence supporting the R29 waiver.

---

# Gate Checklist

- [x] **Gate 0:** scope, Change Ledger, acceptance criteria, and rollback plan reviewed.
- [ ] **Gate 1:** frontend lint and type/build surfaces green.
- [ ] **Gate 2:** focused backend and frontend unit suites green.
- [ ] **Gate 3:** deployed critical journeys and observability verified.
- [x] **Gate 4:** canary not required; additive client/header and log-only change.
- [ ] **Gate 5:** deployed tip and evidence pack attached; R29 waiver disposition recorded.
