# Change Ledger — D-W1-08 Portal intake triage assign + notify

## Summary
Closes P0-INT-2 residual (Journey C): portal `/reports/` submit now auto-assigns a case owner and fires in-app `NotificationService.create_assignment` for incident, complaint, RTA, and near-miss intakes. Builds on #935 unassigned queues + manual PATCH triage; eliminates dead-end ops queue for anonymous portal traffic. FE honesty: `triage_assigned` response flag + success-screen hint when routed.

## What was already LIVE (#935)
- `GET /incidents?owner=unassigned` and `GET /complaints?owner=unassigned` server filters
- Manual `PATCH owner_id` on incidents/complaints with assignment notify
- Incidents/Complaints Unassigned tabs + Dashboard unassigned tile
- Action create notify + bad `assigned_to_email` → 400

## What this PR adds
- `src/domain/services/portal_triage_service.py`: resolve triage owner (staff submitter with update perm, else tenant superuser/admin/manager pool), apply owner, notify
- `src/api/routes/employee_portal.py`: call triage after each portal submit; expose `triage_assigned` on `QuickReportResponse`
- `frontend/src/pages/portalSubmitSuccess.ts` + `PortalIncidentForm.tsx`: honest triage-routed hint when server assigned
- `tests/unit/test_portal_triage_service.py`: pure selection + field-mapping tests

## Change ledger
| File | Change |
|------|--------|
| `src/domain/services/portal_triage_service.py` | NEW — triage owner resolve, assign, notify |
| `src/api/routes/employee_portal.py` | Wire triage on submit; `triage_assigned` response field |
| `frontend/src/pages/portalSubmitSuccess.ts` | `portalTriageRoutedHint()` helper |
| `frontend/src/pages/PortalIncidentForm.tsx` | Success hint when `triage_assigned` |
| `frontend/src/pages/__tests__/portalSubmitSuccess.test.ts` | Triage hint unit test |
| `tests/unit/test_portal_triage_service.py` | NEW — helper unit tests |
| `scripts/governance/pr_body_wc_w1_portal_triage_notify.md` | This ledger |

## Impact map
| Surface | Before (#935) | After |
|---------|---------------|-------|
| Portal POST `/reports/` | Creates case with `owner_id` null → unassigned queue | Auto-assigns triage owner + in-app notify |
| Ops unassigned tab | Catches all portal intakes | Only intakes where no triage owner could be resolved |
| Portal success UX | Generic submitted message | Honest “routed to case owner” when assigned |
| RTA / near-miss portal | No owner on submit | Same triage path (`owner_id` / `assigned_to_id`) |

## Compatibility
- Additive response field `triage_assigned` (optional bool, default false)
- No migration — uses existing `owner_id` / `assigned_to_id` columns
- No SMTP; in-app notify only (same as #935)
- Triage owner resolution is tenant-scoped; fails open (submit still 201) if no eligible user

## Acceptance criteria
- **AC-01**: Portal incident submit sets `owner_id` and creates assignment notification
- **AC-02**: Portal complaint submit sets `owner_id` and creates assignment notification
- **AC-03**: Portal RTA / near-miss submit set `owner_id` / `assigned_to_id` respectively
- **AC-04**: Assigned cases do not appear in `owner=unassigned` list
- **AC-05**: `QuickReportResponse.triage_assigned=true` when owner resolved
- **AC-06**: FE success screen shows triage hint when `triage_assigned`

## Testing evidence
- `tests/unit/test_portal_triage_service.py`
- `frontend/src/pages/__tests__/portalSubmitSuccess.test.ts`

## Critical journeys
- **CUJ-01**: Anonymous portal submit → triage owner assigned → assignee receives in-app assignment notification
- **CUJ-02**: Assigned case excluded from `owner=unassigned` queue → staff opens case from notify (not dead-end ops queue)

## Observability
- Warning log when no triage owner resolvable in tenant
- Exception log on notify failure without undoing committed owner assign

## Release plan
1. Squash-merge after CI green (DO NOT merge from authoring step)
2. Staging auto-deploy; verify portal submit assigns owner in staging DB
3. Production deploy with full release SHA

## Rollback plan
1. Revert squash commit on main
2. Redeploy previous SHA
3. Portal intakes revert to unassigned queue behaviour (#935 manual triage remains)

## Evidence pack
- CI run links attached after push
- Staging portal submit screenshot: pending Gate 3

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — exclusive allowlist only
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack

## Out of scope
- SMTP live send (#853)
- Incidents/Complaints list UI (#935 already LIVE)
- Actions routes, Layout.tsx, RiskRegister, near-miss raise-risk
