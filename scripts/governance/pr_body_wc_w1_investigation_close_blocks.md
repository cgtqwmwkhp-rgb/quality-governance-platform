# Change Ledger — D-W1-10 Investigation closure blocks open CAPA/actions

## Summary
Investigation closure now fails closed when investigation-scoped CAPA/actions remain open. The closure-validation endpoint returns a blocking list with stable reason code `OPEN_ACTIONS_REMAIN`, PATCH `status=closed` is rejected server-side, and InvestigationDetail surfaces honest checklist messaging plus a one-click path to the Actions tab.

## Change ledger
- `investigation_closure_helpers.py` (NEW): query open `investigation_actions`, serialize blockers, `assert_investigation_can_close`
- `investigations.py`: extend `GET /closure-validation`; gate `PATCH` when `status=closed`
- `investigation.py` schema: `open_work` + `open_work_count` on closure-validation response
- `InvestigationDetail.tsx`: blocking list, human reason copy, “Go to Actions tab” unblock CTA
- `investigationsClient.ts`: `ClosureBlockingItem` types
- `test_investigation_closure_gate.py` (NEW): unit proof for gate + reason code stability
- `InvestigationDetail.test.tsx`: closure blocker UI test

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Closure validation API | Level + completed status only | Also lists open investigation actions |
| PATCH close | Always allowed when fields valid | 409 `OPEN_ACTIONS_REMAIN` when actions open |
| Investigation detail checklist | Generic reason codes | Named blockers + Actions tab shortcut |

## Compatibility
- Additive API fields on closure-validation (`open_work`, `open_work_count` default empty/0)
- Existing reason codes unchanged; new stable code `OPEN_ACTIONS_REMAIN`
- No migrations; uses existing `investigation_actions` table

## Acceptance criteria
- **AC-01**: `GET /investigations/{id}/closure-validation` returns `OPEN_ACTIONS_REMAIN` and blocker list when open actions exist
- **AC-02**: `PATCH /investigations/{id}` with `status=closed` returns 409 when open actions exist
- **AC-03**: InvestigationDetail shows blocking list and “Go to Actions tab” when `open_work_count > 0`

## Testing evidence
- `tests/unit/test_investigation_closure_gate.py`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx` (closure blockers)

## Gate checklist
- [x] Gate 0 — change ledger (this file)
- [x] Gate 1 — exclusive allowlist respected
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack attached

## Test plan
- [ ] `pytest tests/unit/test_investigation_closure_gate.py -q`
- [ ] `npm test -- InvestigationDetail.test.tsx`
- [ ] Manual: create investigation action (open) → closure-validation blocked → complete action → can close
