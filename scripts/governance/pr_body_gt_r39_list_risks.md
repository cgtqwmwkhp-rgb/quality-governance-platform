# Change Ledger — Golden-Thread R39: Incident List Risk Links

## Summary
- **Goal:** Return `linked_risk_ids` on every incident list item, matching the existing incident-detail field.
- **Scope:** Incident response schema, focused response-contract tests, and this ledger.
- **Out of scope:** Risk-link creation, link normalization, UI work, migrations, and changes to detail semantics.

## Impact Map
- **API:** `GET /api/v1/incidents/` list-item payloads gain optional `linked_risk_ids`.
- **Schemas:** `IncidentResponse` owns the field, so list and detail response models are aligned.
- **Database:** No change; the existing nullable `incidents.linked_risk_ids` column is read only.
- **Services, jobs, configuration, dependencies:** No change.

## Compatibility
- **Strategy:** Additive optional response field; existing clients can ignore it.
- **Data honesty:** The API exposes the persisted comma-separated legacy value without inventing, resolving, or claiming links that are absent.
- **Breaking changes:** None.
- **Migration plan:** None required.

## Acceptance Criteria
- [x] AC-01: `GET /api/v1/incidents/` items expose `linked_risk_ids`.
- [x] AC-02: A stored value such as `"12,34"` is preserved on the list response.
- [x] AC-03: Incidents without links return `linked_risk_ids: null`, not a fabricated value.
- [x] AC-04: Incident detail continues to expose the same optional field through its inherited response schema.
- [x] AC-05: No database migration is introduced.

## Testing Evidence
- [x] Focused local run (32 passed): `pytest tests/unit/test_incident_list_risk_links.py tests/unit/test_incident_risk_links.py tests/unit/test_gt_openapi_list_routes.py`
- [x] OpenAPI baseline and committed contract remain identical.
- [ ] CI lint/type/full suite: pending PR checks.

## Critical Journeys
- [x] CUJ-01: Risk manager lists incidents and can identify an incident already linked to risks `12,34`.
- [x] CUJ-02: Risk manager lists an incident with no links and receives an explicit `null` rather than a misleading ID.

## Observability
- **Logs:** No change; this is response serialization only.
- **Metrics/alerts:** No change.
- **Runbook:** No update required.

## Release Plan
1. Merge after required CI and review gates pass.
2. Deploy through the normal API release path.
3. Verify `GET /api/v1/incidents/` returns the optional field for a linked and an unlinked incident.

## Rollback Plan
- **Trigger:** List-response compatibility or serialization regression.
- **Owner:** Quality Governance Platform API owner.
- **Rollback steps:** Revert this PR, deploy the reverted release through the normal pipeline, then verify the prior incident list contract is restored.

## Evidence Pack
- Branch base: `f7347bdc` (`main` production tip at branch creation).
- Focused test commands and outcomes: recorded in this ledger and PR checks.
- Migration evidence: none, because no migration is introduced.
- LIVE note: Not LIVE until the PR is merged and deployed; local branch tip is not production.

## Gate Checklist
- [x] **Gate 0:** Scope locked; ledger and acceptance criteria complete.
- [x] **Gate 1:** API/schema contract reviewed; optional field is additive.
- [x] **Gate 2:** Focused unit tests passed locally; CI pending.
- [ ] **Gate 3:** Staging verification pending deployment.
- [x] **Gate 4:** Rollback owner and steps documented.
- [ ] **Gate 5:** PR/CI and LIVE deployment evidence pending.

## Exclusive Change Allowlist
- `src/api/schemas/incident.py`
- `docs/contracts/openapi.json`
- `openapi-baseline.json`
- `tests/unit/test_incident_list_risk_links.py`
- `scripts/governance/pr_body_gt_r39_list_risks.md`
