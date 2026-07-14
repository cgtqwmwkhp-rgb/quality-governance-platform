# Change Ledger — CUJ-OPS-INTAKE-TRIAGE

## Summary
Closes the supervisor handoff for portal intakes: server `owner=unassigned` filters on incidents/complaints, PATCH `owner_id` with `NotificationService.create_assignment`, and `create_action` that fails loudly on unknown `assigned_to_email` while notifying when `owner_id` is set. FE unassigned tabs + SMTP honesty banner; optional Dashboard honest unassigned tile. Draft only — no SMTP invention (#853 parked).

## Change ledger
- `src/domain/models/incident.py` + `alembic/versions/20260713_incidents_owner_id.py`: additive nullable `incidents.owner_id` (complaints already had it)
- `src/api/routes/incidents.py`: `owner=unassigned` list filter; validate `owner_id` on PATCH; notify via `NotificationService.create_assignment`
- `src/api/routes/complaints.py`: same unassigned filter + PATCH owner notify
- `src/api/schemas/incident.py` / `complaint.py`: expose `owner_id` on update/response as needed
- `src/domain/services/incident_service.py`: additive `owner` list filter glue
- `src/api/routes/actions.py`: fail loudly on bad `assigned_to_email`; notify hook on create/update when owner set
- `frontend/src/api/incidentsClient.ts` / `complaintsClient.ts`: pass `owner` query + `owner_id` update
- `frontend/src/pages/Incidents.tsx` / `Complaints.tsx`: Unassigned tab, assign owner, SMTP honesty banner
- `frontend/src/pages/Dashboard.tsx`: one honest unassigned intakes tile (server totals)
- `frontend/src/i18n/locales/en.json` + `cy.json`: triage keys only
- `tests/integration/test_ops_intake_triage_cuj.py`: intake → assign → notify → bad email 400
- `frontend/tests/e2e/ops-intake-triage-cuj.spec.ts`: mocked Playwright CUJ
- `scripts/governance/pr_body_cuj_ops_intake_triage.md`: this ledger

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Incident/complaint list | No unassigned server filter | `owner=unassigned` |
| Case owner assign | DB field unused / silent | PATCH `owner_id` + in-app assignment notify |
| Action assign email | Unknown email → unowned 201 | 400 Bad Request |
| Action create with owner | No notify | `NotificationService.create_assignment` |
| FE triage | Manual hunting | Unassigned tabs + assign UI + SMTP honesty |
| Dashboard | Client page-1 theatre for queues | Honest server unassigned totals tile |

## Compatibility
- Additive API query/body fields (optional)
- Additive migration: nullable `incidents.owner_id` (complaints already had `owner_id`)
- No SMTP / outbound email claims; in-app notify only
- Avoids GKB, Workforce, AnimatedOutlet, SWA workflow, PortalWork.tsx

## Acceptance criteria
- **AC-01**: `GET /incidents?owner=unassigned` and `GET /complaints?owner=unassigned` return only rows with null `owner_id`
- **AC-02**: `PATCH` owner_id on incident/complaint creates assignment notification for the assignee
- **AC-03**: `POST /actions` with unknown `assigned_to_email` returns 400 (not silent unowned 201)
- **AC-04**: `POST /actions` with valid assignee calls `create_assignment` (notification row)
- **AC-05**: Incidents/Complaints Unassigned tab calls server filter and shows SMTP honesty when email unconfigured
- **AC-06**: Dashboard unassigned tile uses server `owner=unassigned` totals

## Testing evidence
- `tests/integration/test_ops_intake_triage_cuj.py`
- `frontend/tests/e2e/ops-intake-triage-cuj.spec.ts`

## Critical journeys
- **CUJ-01**: Portal intake → Unassigned tab → assign case owner → in-app notify
- **CUJ-02**: Create action with assignee → notify → visible to My Work (assignee filter path)
- **CUJ-03**: Bad assignee email fails loudly (400)

## Observability
- Existing route logs retained; notify failures logged without undoing committed assigns
- Playwright hooks: `incidents-filter-unassigned`, `complaints-filter-unassigned`, `*-email-unavailable`, `dashboard-unassigned-intakes`

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
- AC-01..AC-04: integration CUJ
- AC-05: Playwright mocked triage
- AC-06: Dashboard tile wiring
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

## Out of scope
- SMTP live send (#853)
- GKB / Workforce / SWA workflow / PortalWork / AnimatedOutlet
- Full IMS redesign
