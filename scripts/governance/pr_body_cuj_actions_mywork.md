# Change Ledger — CUJ Actions My Work / Overdue server filters

## Summary
Wires Actions **My Work** and **Overdue** view modes to honest server-side list filters (`assigned_to=me`, `overdue=true`) instead of client-only page slicing. Filter failures toast + label (no silent empty). Preserves Wave B incident/investigation scoped playbooks from #907. No SMTP invention (#853 parked).

## Change ledger
- `src/api/routes/actions.py`: additive `assigned_to` + `overdue` query params on `GET /api/v1/actions/`; SQL owner/due filters across incident/RTA/complaint/investigation/CAPA list + count paths
- `frontend/src/api/actionsClient.ts`: pass `assigned_to` / `overdue` scope params (required glue for server filters)
- `frontend/src/pages/Actions.tsx`: My/Overdue reload via server scope; identity/filter failure toast + alert; server-filter honesty label; keep incident/investigation playbooks
- `frontend/src/pages/__tests__/Actions.test.tsx`: My/Overdue param + failure toast coverage
- `frontend/src/api/actionsClient.test.ts`: scope query-string coverage
- `frontend/tests/e2e/actions-my-work-cuj.spec.ts`: mocked Playwright CUJ
- `frontend/src/i18n/locales/en.json` + `cy.json`: `actions.filter.*` keys only
- `scripts/governance/pr_body_cuj_actions_mywork.md`: this ledger

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| My actions | Client filter on first page (`owner_id === sub`) | Server `assigned_to=me` |
| Overdue | Client filter on first page (`due_date < now`) | Server `overdue=true` (past due, not done) |
| Filter failure | Silent empty / generic error | Toast + visible alert; identity missing called out |
| Scoped playbooks | Incident/investigation Wave B cards | Unchanged |

## Compatibility
- Additive API query params (optional; default behaviour unchanged)
- No schema/migration changes
- No SMTP / notification delivery claims
- RR 6.30: no `NavLink` `isActive` usage introduced

## Acceptance criteria
- **AC-01**: Selecting My actions calls list with `assigned_to=me` and shows server-filter label
- **AC-02**: Selecting Overdue calls list with `overdue=true` and shows server-filter label
- **AC-03**: Failed My/Overdue list request toasts and does not silently present an empty success state
- **AC-04**: Incident/investigation scoped playbooks from #907 still render for `sourceType` + `sourceId`

## Testing evidence
- `frontend/src/pages/__tests__/Actions.test.tsx` — My/Overdue params + failure toast
- `frontend/src/api/actionsClient.test.ts` — scope query string
- `frontend/tests/e2e/actions-my-work-cuj.spec.ts` — mocked Playwright CUJ

## Critical journeys
- **CUJ-01**: Actions → My actions → server `assigned_to=me` + honesty label
- **CUJ-02**: Actions → Overdue → server `overdue=true` (+ failure path toast/label)
- **CUJ-03**: Actions scoped `sourceType=incident|investigation` playbooks still present (#907)

## Observability
- Existing `list_actions` per-source warning logs retained
- Playwright hooks: `actions-view-mode`, `actions-view-my`, `actions-view-overdue`, `actions-server-filter-label`, `actions-filter-error`

## Release plan
1. Squash-merge to main after CI green (DO NOT merge from this PR authoring step)
2. Staging auto-deploy via CI workflow_run
3. Confirm staging tip + `/healthz` 200 (2×)
4. Force-deploy production with full 40-char `release_sha` (freeze window)

## Rollback plan
1. Revert squash commit on main
2. Redeploy previous known-good SHA via production workflow_dispatch
3. Verify `/api/v1/meta/version` matches rollback SHA

## Evidence pack
- AC-01: Actions unit + Playwright My path
- AC-02: Actions unit + Playwright Overdue path
- AC-03: Actions unit failure toast; Playwright overdue failure visibility
- AC-04: Wave B playbook markup retained in Actions.tsx
- Gate 0: Change ledger present (this file)
- Gate 1: Exclusive allowlist respected (Actions + actions list filters + i18n filter keys + ledger; client glue required)
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
- [ ] `npm test -- Actions actionsClient` (frontend unit)
- [ ] `npx playwright test actions-my-work-cuj.spec.ts`
- [ ] Manual: Actions → My / Overdue labels + network query params
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy

## Out of scope / parked
- #853 SMTP — parked; no invented outbound email
- Locked exclusive surfaces: IMSDashboard (#908), near_miss/tenant inventory (#909), Complaint (#910), RTADetail (#911), UVDBAudits/assuranceHubHelpers/external_audit_promotion (#912), ComplianceEvidence (#913), syncService.test.ts (#914)
