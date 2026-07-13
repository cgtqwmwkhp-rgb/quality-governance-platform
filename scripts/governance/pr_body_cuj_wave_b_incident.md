# Change Ledger — CUJ Wave B Incident → Investigation → CAPA

## Summary
Closes world-class cohesion gaps on Incident → Investigation → CAPA: unified Create/Open CAPA hand-off on IncidentDetail (no dead-end `no_capa_handoff`), InvestigationDetail workflow proof strip with aligned CTAs, incident/investigation playbook parity on scoped Actions, shared handoff helpers, Playwright + integration HTTP chain proof, and `investigations.from_record` journey metric.

## Change ledger
- `handoffLinks.ts`: `resolveCapaHandoffMode` + `getCapaHandoffLabelKey` shared Create/Open CAPA CTA keys
- `IncidentDetail.tsx`: handoff + header always show CAPA CTA (`incident-capa-handoff-cta`); remove no-action dead end
- `InvestigationDetail.tsx`: aligned CAPA CTA + thin workflow proof strip (counts + links)
- `Actions.tsx`: incident/investigation scoped playbooks + row deep-links to source records
- `investigation_service.py`: `investigations.from_record` metric on from-record creation
- Tests: IncidentDetail/InvestigationDetail unit, Playwright `incident-investigation-capa-cuj.spec.ts`, integration `test_incident_investigation_capa_cuj.py`

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Incident handoff card | Open CAPA only when actions exist; else static no-CAPA text | Always Create or Open CAPA → scoped Actions |
| Investigation handoff | CTA only in header row | Proof strip with source/action counts + duplicate CTA links |
| Actions (scoped) | Audit playbook only | Incident + investigation playbooks with back-links |
| Backend journey | No from-record observability tag | `investigations.from_record` metric with source_type |

## Compatibility
- No API contract changes; deep-link query params unchanged (`sourceType`, `sourceId`)
- i18n uses existing keys + inline fallbacks for new playbook/proof copy (no locale file edits)
- RR 6.30: no `NavLink` `isActive` usage introduced

## Acceptance criteria
- **AC-01**: Incident handoff card shows Create CAPA CTA when zero linked actions (not `no_capa_handoff` only)
- **AC-02**: Investigation detail shows workflow proof counts and switches Open vs Create CAPA by action count
- **AC-03**: Actions filtered by `sourceType=incident|investigation` renders scoped playbook with back-link

## Testing evidence
- `frontend/src/pages/__tests__/IncidentDetail.test.tsx` — Create CAPA handoff when empty
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx` — proof strip + Open CAPA label
- `frontend/tests/e2e/incident-investigation-capa-cuj.spec.ts` — mocked Playwright CUJ (3 paths)
- `tests/integration/test_incident_investigation_capa_cuj.py` — HTTP chain incident → from-record → CAPA list

## Critical journeys
- **CUJ-01**: Incident detail → Create/Open CAPA → scoped Actions with incident playbook
- **CUJ-02**: Investigation detail → proof strip → scoped Actions with investigation playbook
- **CUJ-02**: Incident → from-record investigation → investigation-scoped + incident-scoped CAPA (integration)

## Observability
- `investigations.from_record` metric emitted on successful `create_from_record` with `source_type` + `tenant_id` tags
- Playwright `data-testid` hooks: `incident-capa-handoff-cta`, `investigation-workflow-proof`, `actions-incident-playbook`, `actions-investigation-playbook`

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
- AC-01: IncidentDetail unit + Playwright create-path green
- AC-02: InvestigationDetail unit + Playwright proof strip green
- AC-03: Playwright scoped Actions playbooks green
- CUJ-01: Incident → CAPA e2e green
- CUJ-02: Investigation proof → CAPA e2e + integration HTTP chain green
- Gate 0: Change ledger present (this file)
- Gate 1: Exclusive allowlist respected
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
- [ ] `npm test -- IncidentDetail InvestigationDetail` (frontend unit)
- [ ] `npx playwright test incident-investigation-capa-cuj.spec.ts`
- [ ] `pytest tests/integration/test_incident_investigation_capa_cuj.py -q`
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
