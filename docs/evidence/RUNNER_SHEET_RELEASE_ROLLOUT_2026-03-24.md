# Runner Sheet Release Rollout

Date: 2026-03-24  
Owner: Platform Engineering

## Scope

This rollout covers:

- timestamped runner-sheet persistence for incidents, complaints, dedicated near misses, and RTAs
- governed runner-sheet CRUD endpoints with tenant-aware access controls
- consistent case-detail runner-sheet UX across the admin application
- dedicated near-miss admin list/detail pages with runner-sheet support

## Candidate Build

- backend route, schema, and model changes are included in the candidate SHA
- frontend runner-sheet UX changes are included in the candidate SHA
- PR governance, accessibility, and localization repairs are included in the candidate SHA

## Pre-Staging Gates

- CI must pass on the candidate SHA
- frontend lint, typecheck, and i18n validation must pass
- runner-sheet route tests must pass
- no unresolved lint errors on changed files

## Staging Validation

1. Confirm staging deploy completed successfully using the standard deployment workflow.
2. Verify database migrations reached Alembic head.
3. Confirm `/healthz`, `/readyz`, and `/api/v1/meta/version` are healthy.
4. Open one incident record and verify runner-sheet list, add, and delete flows.
5. Open one complaint record and verify runner-sheet list, add, and delete flows.
6. Open one RTA record and verify runner-sheet list, add, and delete flows.
7. Open `/near-misses`, navigate to a near-miss detail record, and verify list, add, and delete flows.
8. Confirm unauthorized delete attempts are blocked for non-authorized users.
9. Confirm timestamps and actor attribution render correctly in the UI.
10. Confirm no regression in existing investigation creation flows from incident, complaint, near miss, and RTA detail pages.

## Production Promotion Gates

- staging validation checklist completed
- UAT sign-off recorded with runner-sheet validation evidence
- CAB / governance sign-off recorded if required by release policy
- production deploy uses the same validated SHA
- rollback owner identified before promotion

## Production Validation

1. Verify production deploy references the intended SHA.
2. Re-run controlled runner-sheet add/list/delete checks on one case per module where permitted.
3. Confirm near-miss admin list/detail pages load correctly in production.
4. Monitor API failures, 403/404 error rates, and runner-sheet create/delete events during the initial bake window.

## Audit / Observability Note

- Runner-sheet mutations emit the platform's current `record_audit_event(...)` helper.
- This provides observability-grade audit telemetry today.
- Durable database-backed audit persistence is a follow-on hardening item if compliance requires immutable persisted audit records for these events.

## Rollback

Immediate mitigation:

1. Revert the runner-sheet rollout PR on `main`.
2. Redeploy the prior approved production artifact.
3. Re-verify `/healthz`, `/readyz`, and `/api/v1/meta/version`.
4. Confirm legacy case detail pages still load and runner-sheet tabs are removed or reverted as expected.

## Evidence To Attach To PR / Release

- CI run URL
- staging deployment URL and validation screenshots or API transcripts
- final release SHA
- completed staging validation checklist
- production validation notes
- rollback owner and decision log
