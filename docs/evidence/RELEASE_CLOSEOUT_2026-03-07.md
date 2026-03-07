# Release Closeout - 2026-03-07

## Outcome

- Deployment promotion completed and verified.
- Staging and production are aligned to the same runtime build SHA:
  - `6006e58c293cd1fc946ca602380a6059fcd070b1`

## Evidence Index

- PR merged: [PR #265](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/265)
- Staging deployment success (parity target SHA):
  - [Run 22798363802](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/22798363802)
- Production deployment success (manual dispatch, pinned release SHA):
  - [Run 22798719532](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/22798719532)
- Production runtime identity verification:
  - `GET https://app-qgp-prod.azurewebsites.net/api/v1/meta/version`
  - returned `build_sha=6006e58c293cd1fc946ca602380a6059fcd070b1`
- Governance sign-off artifact used by production gate:
  - `docs/evidence/release_signoff.json`

## Governance/Process Findings

1. Production gate behavior was correct and blocked non-compliant promotion when sign-off SHA did not match.
2. Auto-triggered production runs can target a newer `workflow_run` SHA than the intended parity SHA if `main` advances.
3. Parity promotion is deterministic when production is manually dispatched with explicit `release_sha`.

## Corrective Actions Applied

- Added production workflow support for manual SHA pinning:
  - `workflow_dispatch` input `release_sha`
  - Release SHA resolution logic now honors that input when provided.
- Updated and validated `docs/evidence/release_signoff.json` to match the promoted SHA.
- Executed manual production dispatch pinned to the validated staging SHA.

## Standardized Next-Time Checklist

1. Confirm target promotion SHA from staging success run.
2. Generate/update `docs/evidence/release_signoff.json` for that exact SHA.
3. Validate artifact:
   - `python3 scripts/governance/validate_release_signoff.py --file docs/evidence/release_signoff.json --sha <TARGET_SHA>`
4. Trigger production with explicit SHA pin:
   - `gh workflow run deploy-production.yml --ref main -f staging_verified=true -f release_sha=<TARGET_SHA> -f reason="Parity promotion"`
5. Verify runtime identity in both environments and archive links in evidence docs.

## Residual Risk

- If commits continue landing on `main` during promotion, auto-triggered production runs may drift to a different SHA.
- Mitigation: use explicit `release_sha` pinning for parity-sensitive promotions.
