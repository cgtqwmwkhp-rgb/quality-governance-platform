# Audit UAT and CAB Runbook (Strict Gate)

Version: 1.0  
Owner: Governance Lead + Platform Engineering

## Objective

Provide a deterministic, auditable path for UAT and CAB sign-off before production deployment of audit functionality.

## Inputs

- Candidate SHA (`RELEASE_SHA`)
- Staging deployment URL
- Test user credentials for governance UAT
- Contract freeze reference: `docs/contracts/AUDIT_LIFECYCLE_CONTRACT.md`

## Mandatory UAT Checklist

1. **Published template dropdown**
   - Open Audit scheduling modal.
   - Confirm only published templates are shown.
   - Confirm dropdown option format includes version.
2. **Version parity**
   - Schedule run from a known template version.
   - Confirm `v{template_version}` appears on board/list rows.
3. **Entity rendering**
   - Validate question/template text with `&` renders cleanly (no `&amp;` in UI).
4. **Lifecycle**
   - Schedule run, submit response, complete run, create finding.
   - Raise and close follow-up action via corrective-action bridge flow.
5. **Negative checks**
   - Unpublished template cannot be used for run creation.
   - Duplicate response to same question is rejected.

## CAB Approval Criteria

- All mandatory UAT checks passed.
- Staging smoke and lifecycle E2E checks passed.
- Observability checks green (no unexplained 4xx/5xx spikes).
- Rollback drill evidence current and valid.
- Release sign-off artifact updated for `RELEASE_SHA`.

## Sign-off Artifact

Before production deploy, create:

- `docs/evidence/release_signoff.json` (from template)

Required fields:

- `release_sha`
- `governance_lead`
- `governance_lead_approved` = true
- `cab_chair`
- `cab_approved` = true
- `uat_report_path`
- `rollback_drill_path`
- `approved_at_utc`

## Enforcement

Production workflow blocks if sign-off artifact is missing, malformed, or references a different SHA.
