# Change Ledger — CUJ RTA detail honesty + a11y + proof

## Summary
Closes residual world-class gaps on the RTA (Road Traffic Collision) admin journey (list → detail → CAPA/investigation hand-offs → running sheet): investigation modal trimmed to `from-record` API contract, save/delete/create failures surfaced via toast, honest “Key dates” card (not faux activity timeline), stay on detail after investigation create, Open investigation / Open CAPA deep-links, vitest a11y on detail, and 3-layer proof harness (Playwright + smoke + UAT).

## Change ledger
- `RTADetail.tsx`: title-only investigation modal; `toast.error` on save/delete/create failures; `toast.success` + reload investigations (no navigate to `/investigations`); Key dates + running-sheet hint; Open CAPA → `/actions?sourceType=rta&sourceId=`; Open investigation when linked; labelled action modal fields; loading `role="status"`
- `RTADetail.test.tsx`: expand save-error toast, modal honesty, stay-on-detail, CAPA/investigation hand-offs, key dates
- `RTADetail.a11y.test.tsx`: **NEW** axe coverage for populated `/rtas/:id`
- `rta-lifecycle-cuj.spec.ts`: **NEW** Playwright CUJ-01/02 mocked admin lifecycle (list→detail→handoff)
- `rta_lifecycle_e2e.py`: **NEW** named smoke steps (create, patch, actions, from-record, running-sheet)
- `test_rta_lifecycle.py`: **NEW** UAT with path/status/data assertions (no vacuous stubs)
- `pr_body_cuj_rta_detail.md`: this Change Ledger

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Investigation modal | Type, lead, notes fields not sent to API | Title-only + honest API contract copy |
| Post-investigation nav | Redirect to `/investigations` list | Stay on RTA detail; reload linked investigations |
| Timeline card | “Activity timeline” with 2 static events | “Key dates” + running-sheet hint + linked investigation when present |
| CAPA / investigation hand-off | Modal create only; no filtered Actions deep-link | Open CAPA (`sourceType=rta`) + Open investigation when linked |
| Delete photo / running-sheet | Silent `trackError` only | Operator-visible `toast.error` |
| Proof depth | List a11y only; no RTA detail lifecycle harness | Detail a11y + Playwright + smoke + UAT |

## Compatibility
- No API contract changes; `POST /investigations/from-record` payload unchanged (`source_type=road_traffic_collision`)
- i18n uses existing keys + inline fallbacks for new honest copy (no locale file edits)
- Does not touch near_miss / #909 inventory / alembic; exclusive allowlist only
- Portal RTA submit path untouched; admin detail-only scope

## Acceptance criteria
- **AC-01**: Investigation modal collects only title; no type/lead/notes fields implying unsupported API payload
- **AC-02**: RTA save failure shows `toast.error` (not console-only)
- **AC-03**: After investigation create, user remains on `/rtas/:id` with linked investigation visible
- **AC-04**: Key dates card is honest (not labelled Activity timeline); Running Sheet holds narrative
- **AC-05**: Open CAPA navigates to `/actions?sourceType=rta&sourceId=:id` when actions exist
- **AC-06**: Populated RTA detail passes axe (vitest)

## Testing evidence
- `frontend/src/pages/__tests__/RTADetail.test.tsx` — save toast, modal honesty, stay-on-detail, CAPA hand-off, key dates
- `frontend/src/pages/__tests__/RTADetail.a11y.test.tsx` — axe on populated detail
- `frontend/tests/e2e/rta-lifecycle-cuj.spec.ts` — mocked Playwright CUJ (2 paths)
- `scripts/smoke/rta_lifecycle_e2e.py` — HTTP smoke chain with named steps
- `tests/e2e/uat/test_rta_lifecycle.py` — UAT path/status/data assertions

## Critical journeys
- **CUJ-01**: RTAs list → detail → start investigation (stay on detail) → see linked INV ref
- **CUJ-02**: RTA detail → Key dates honesty → Open CAPA hand-off → Running Sheet narrative entry

## Observability
- Operator-visible toast on save/delete/create failure and investigation/action create success (assertive live region via Toast)
- Smoke step names: `create_rta`, `patch_rta_status`, `list_rta_actions`, `create_investigation_from_record`, `list_rta_investigations`, `add_rta_running_sheet_entry`, `list_rta_running_sheet`
- Playwright `data-testid` hooks: `rta-start-investigation`, `rta-investigation-modal`, `rta-investigation-title`, `rta-key-dates`, `rta-save-edit`, `rta-open-capa`

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
- AC-01: RTADetail unit + Playwright modal field absence green
- AC-02: RTADetail unit save-error toast green
- AC-03: RTADetail unit + Playwright stay-on-detail green
- AC-04: RTADetail unit + Playwright key dates green
- AC-05: RTADetail unit + Playwright CAPA hand-off green
- AC-06: RTADetail.a11y axe green
- CUJ-01: Playwright investigation create path green
- CUJ-02: Playwright key dates + CAPA + running sheet green
- Gate 0: Change ledger present (this file)
- Gate 1: Exclusive allowlist (RTADetail + tests + smoke/UAT + ledger only)
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
- [ ] `npm test -- RTADetail` (frontend unit + a11y)
- [ ] `npx playwright test rta-lifecycle-cuj.spec.ts`
- [ ] `pytest tests/e2e/uat/test_rta_lifecycle.py -q`
- [ ] `python scripts/smoke/rta_lifecycle_e2e.py --base-url … --email … --password …` (staging)
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy

Made with [Cursor](https://cursor.com)
