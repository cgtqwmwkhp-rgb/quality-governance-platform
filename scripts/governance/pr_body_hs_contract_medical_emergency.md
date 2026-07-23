## Summary
Wire Incident **Customer/contract** as a real dropdown FK, promote portal **medical assistance** codes to a first-class column, and add a separate **emergency services** multi-select — so care pathway and emergency attendance stay distinct and correctly persisted.

## Change Ledger
| Area | Change |
|---|---|
| Schema | `incidents.contract_id` FK → `contracts`; `medical_assistance`; `emergency_services` JSON; seed `emergency_services` lookup |
| API | Create/update/response expose new fields; tenant contract guard; derive `first_aid_given` / `emergency_services_called` from source fields |
| Portal | Resolve customer code → `contract_id`; promote medical + emergency list; emergency multi-select UI |
| Staff UI | Incident create requires customer dropdown; detail edit medical dropdown + emergency multi-select |
| Complaints | Selecting customer sets `contract_id` (no longer forced null) |
| Import | Excel medical Y/N → medical code; optional contract resolve by customer text |

## Impact Map
- Incident create/edit/detail + portal incident intake
- Complaint create customer selection
- Admin Lookups (+ Emergency Services category)
- Alembic head → `20260812_hs_cme`

## Compatibility
- Legacy rows keep null `contract_id` / medical / emergency
- Existing booleans remain; when medical/emergency source fields are written they re-derive the booleans
- Medical=`ambulance` no longer auto-sets emergency_services_called

## Acceptance Criteria
- AC-01: Staff create requires Customer/contract dropdown → persists `contract_id`
- AC-02: Staff edit medical dropdown persists `medical_assistance` and updates `first_aid_given`
- AC-03: Staff/portal emergency multi-select persists `emergency_services` and `emergency_services_called` independently of medical
- AC-04: Portal submit with customer code resolves/creates tenant contract FK when possible
- AC-05: Complaint create sets `contract_id` when customer code matches a contract

## Testing Evidence
- Unit: `tests/unit/test_incident_care_fields.py`
- Manual: create incident with customer; set medical + police/ambulance; confirm detail view labels

## Critical Journeys
- CUJ-01: Portal injury report with medical + emergency services → staff detail shows both correctly
- CUJ-02: Staff create with customer → list/detail shows contract name
- CUJ-03: Complaint create with customer → `contract_id` populated

## Observability
- Invalid cross-tenant `contract_id` → ValueError / 4xx via existing service paths

## Release Plan
1. Merge squash to main
2. Alembic migrates columns + seeds emergency_services lookup
3. Confirm tip==LIVE; smoke portal + staff incident create/edit

## Rollback Plan
- Owner: Platform / H&S
- Rollback steps: revert deploy; optional downgrade drops new columns

## Evidence Pack
- PR diff + unit tests + post-deploy smoke of create/edit/portal

## Gate Checklist
- Gate 0: Scope locked (contract FK + medical + emergency)
- Gate 1: Schema + API + UI wired
- Gate 2: Unit tests green
- Gate 3: CI green
- Gate 4: tip==LIVE
- Gate 5: Portal + staff smoke verified
