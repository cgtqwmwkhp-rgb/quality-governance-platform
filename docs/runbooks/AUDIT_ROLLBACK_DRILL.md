# Audit Rollback Drill Runbook

Version: 1.0  
Owner: Platform Engineering  
Frequency: Before each high-risk production release

## Goal

Demonstrate that the platform can rollback audit-related releases safely within target recovery time.

## Preconditions

- Production deployment proof artifact exists for current release.
- Immutable release SHA is known (`RELEASE_SHA`).
- Previous known-good SHA is identified (`ROLLBACK_SHA`).
- CAB notified of drill window.

## Drill Steps

1. Record baseline health (`/healthz`, `/readyz`, audit endpoint smoke).
2. Trigger rollback deployment to `ROLLBACK_SHA` image tag.
3. Verify deterministic SHA endpoint returns `ROLLBACK_SHA`.
4. Run smoke checks:
   - `scripts/smoke/post_deploy_check.py`
   - `scripts/smoke/audit_lifecycle_e2e.py`
5. Capture recovery time (start -> all checks green).
6. Re-promote latest approved release if drill-only rollback.

## Success Criteria

- Recovery completed in <= 15 minutes.
- No unresolved 5xx spikes after rollback.
- Audit scheduling, version display, and finding flow remain operational.
- Evidence artifact committed and attached to CAB notes.

## Evidence Artifact

Create and store:

- `docs/evidence/ROLLBACK_DRILL_<YYYYMMDD>.md`

Include:

- Drill operator
- Start/end timestamps
- Target SHA + rollback SHA
- Verification outputs
- Issues found and follow-up actions
