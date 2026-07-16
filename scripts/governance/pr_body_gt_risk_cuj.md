# Change Ledger (CL-GT-RISK-CUJ-R60-R32-R61)

## Scope lock

- **In scope:** Risk Register band-count fallback for populated heat-map data; Incident Detail evidence-asset aggregation and display; targeted frontend tests; this Change Ledger.
- **Out of scope:** schema changes, data seeding/backfill, changes to incident/CAPA/risk linkage creation, and unrelated UAT remediation.

## Findings

- **R60:** A legacy or stale `/risk-register/summary` response can carry `total_risks` without `by_level`. The UI rendered missing band fields as zero despite populated heat-map cells. Counts now derive from heat-map cells only when band counts are absent.
- **R32:** Incident Detail already requests source-filtered actions and receives `linked_risk_ids` from the incident detail endpoint. Empty actions and linked risks for `INC-2` are tenant-data outcomes unless the underlying records/links exist.
- **R61:** Incident Detail previously displayed only `reporter_submission.photos.count`; it never queried evidence assets with `source_module=incident`. Existing incident evidence could therefore appear empty. The detail view now surfaces linked evidence assets.

## Acceptance criteria

- [x] R60: Missing summary bands do not render as false zeros when heat-map cells contain risks.
- [x] R61: Incident detail loads and lists evidence assets for its incident ID.
- [x] R32: Existing action and linked-risk aggregation paths were verified; no unnecessary schema or linkage change.
- [x] Targeted tests cover the heat-map fallback and incident evidence path.

## Verification

- `npm test -- --run src/pages/__tests__/RiskRegister.test.tsx src/pages/__tests__/IncidentDetail.test.tsx`
- `npm run typecheck`

## Allowed files

- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/__tests__/RiskRegister.test.tsx`
- `frontend/src/pages/__tests__/IncidentDetail.test.tsx`
- `scripts/governance/pr_body_gt_risk_cuj.md`
