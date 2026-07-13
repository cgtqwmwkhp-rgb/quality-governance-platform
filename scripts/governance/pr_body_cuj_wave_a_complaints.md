# Change Ledger — CUJ Wave A Complaints honesty + proof

## Summary
Closes residual world-class gaps on Complaint admin lifecycle (list → detail → status → action → investigation → running sheet): investigation modal trimmed to `from-record` API contract, save failures surfaced via toast, honest “Key dates” card (not faux audit timeline), stay on detail after investigation create, and 3-layer proof harness (Playwright + smoke + UAT) plus running-sheet audit unit test.

## Change ledger
- `ComplaintDetail.tsx`: trim investigation modal to title-only `createFromRecord`; `toast.error` on save failure; `toast.success` + reload investigations (no navigate away); relabel timeline → Key dates with running-sheet hint
- `complaint-lifecycle-cuj.spec.ts`: **NEW** Playwright CUJ-01/02 mocked admin lifecycle
- `complaint_lifecycle_e2e.py`: **NEW** named smoke steps (create, patch, actions, from-record, running-sheet)
- `test_complaint_lifecycle.py`: **NEW** UAT with path/status/data assertions (no vacuous stubs)
- `ComplaintDetail.test.tsx`: expand save-error toast, modal honesty, stay-on-detail, key dates
- `test_runner_sheet_routes.py`: add `test_add_complaint_running_sheet_entry_records_audit_and_tenant`

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Investigation modal | Type, lead, notes fields not sent to API | Title-only + honest API contract copy |
| Save edit failure | `console.error` only | Operator-visible `toast.error` |
| Post-investigation nav | Redirect to `/investigations` list | Stay on complaint detail; reload linked investigations |
| Timeline card | “Activity timeline” with 2 static events | “Key dates” + running-sheet hint + linked investigation when present |
| Proof depth | No Playwright/smoke/UAT admin lifecycle | 3-layer harness + running-sheet audit unit test |

## Compatibility
- No API contract changes; `POST /investigations/from-record` payload unchanged
- i18n uses existing keys + inline fallbacks for new honest copy (no locale file edits)
- Portal CUJ-09 submit path untouched; admin detail-only scope

## Acceptance criteria
- **AC-01**: Investigation modal collects only title; no type/lead/notes fields implying unsupported API payload
- **AC-02**: Complaint save failure shows `toast.error` (not console-only)
- **AC-03**: After investigation create, user remains on `/complaints/:id` with linked investigation visible

## Testing evidence
- `frontend/src/pages/__tests__/ComplaintDetail.test.tsx` — save toast, modal honesty, stay-on-detail, key dates
- `frontend/tests/e2e/complaint-lifecycle-cuj.spec.ts` — mocked Playwright CUJ (2 paths)
- `scripts/smoke/complaint_lifecycle_e2e.py` — HTTP smoke chain with named steps
- `tests/e2e/uat/test_complaint_lifecycle.py` — UAT path/status/data assertions
- `tests/unit/test_runner_sheet_routes.py` — complaint running-sheet create audit event

## Critical journeys
- **CUJ-01**: Complaint detail → acknowledge/status edit → start investigation (stay on detail) → see linked INV ref
- **CUJ-02**: Complaint detail → Key dates honesty → Running Sheet narrative entry

## Observability
- Operator-visible toast on save failure and investigation create success (assertive live region via Toast)
- Smoke step names: `create_complaint`, `patch_complaint_status`, `list_complaint_actions`, `create_investigation_from_record`, `list_complaint_investigations`, `add_complaint_running_sheet_entry`, `list_complaint_running_sheet`
- Playwright `data-testid` hooks: `complaint-start-investigation`, `complaint-investigation-modal`, `complaint-investigation-title`, `complaint-key-dates`, `complaint-save-edit`

## Release plan
1. Squash-merge to main after CI green
2. Staging auto-deploy via CI workflow_run
3. Confirm staging tip + `/healthz` 200 (2×)
4. Force-deploy production with full 40-char `release_sha` (freeze window)

## Rollback plan
1. Revert squash commit on main
2. Redeploy previous known-good SHA via production workflow_dispatch
3. Verify `/api/v1/meta/version` matches rollback SHA

## Evidence pack
- AC-01: ComplaintDetail unit + Playwright modal field absence green
- AC-02: ComplaintDetail unit save-error toast green
- AC-03: ComplaintDetail unit + Playwright stay-on-detail green
- CUJ-01: Playwright investigation create path green
- CUJ-02: Playwright key dates + running sheet green
- Gate 0: Change ledger present (this file)
- Gate 1: Exclusive allowlist (7 files only)
- Gate 2: CI required checks
- Gate 3: Staging tip==SHA
- Gate 4: Prod tip==SHA
- Gate 5: Evidence recorded in this PR

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — allowlist only
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack attached

## Test plan
- [ ] `npm test -- ComplaintDetail` (frontend unit)
- [ ] `npx playwright test complaint-lifecycle-cuj.spec.ts`
- [ ] `pytest tests/unit/test_runner_sheet_routes.py -q -k complaint`
- [ ] `pytest tests/e2e/uat/test_complaint_lifecycle.py -q`
- [ ] `python scripts/smoke/complaint_lifecycle_e2e.py --base-url … --email … --password …` (staging)
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
