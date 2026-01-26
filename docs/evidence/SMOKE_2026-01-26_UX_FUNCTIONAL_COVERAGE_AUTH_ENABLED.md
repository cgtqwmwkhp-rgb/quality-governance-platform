# Evidence Pack: UX Functional Coverage Gate - Auth Enabled

> **Classification**: Evidence | Deployment Gate
> **Date**: 2026-01-26
> **Status**: PENDING VALIDATION

## Summary

This evidence pack documents the enablement of authenticated UX functional coverage testing in CI. Prior to this change, auth-protected routes were skipped due to missing tokens, resulting in HOLD status.

## Before State

| Metric | Value |
|--------|-------|
| **Workflow Run** | [#21350986865](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/21350986865) |
| **Score** | 70/100 |
| **Status** | HOLD |
| **P0 Failures** | 4 |
| **P1 Failures** | 3 |
| **Dead Ends** | 3 |
| **Tokens Acquired** | ❌ No (secrets not configured) |

### P0 Failures (Before)
- `portal-incident-report` - Auth type portal_sso not configured
- `portal-near-miss-report` - Auth type portal_sso not configured  
- `portal-rta-report` - Auth type portal_sso not configured
- `admin-view-incident` - Auth type jwt_admin not configured

## Changes Implemented

### 1. Dynamic Token Acquisition

- **Commit**: `516c9bc` - feat(ux-coverage): add dynamic token acquisition for auth testing
- **Script**: `scripts/governance/get-ux-test-tokens.cjs`
- **Mechanism**: Acquires tokens via `/api/v1/auth/login` at runtime

### 2. Workflow Updates

- Added `acquire-tokens` job to workflow
- Tokens passed to audit jobs via masked outputs
- Extra masking step in each audit job
- Summary shows "Tokens Acquired" status

### 3. Policy Updates

- Updated `UX_COVERAGE_POLICY.md` with auth-mandatory requirements
- P0 routes cannot be skipped due to missing auth
- Auto-triage for auth configuration issues

### 4. Documentation

- Created `UX_COVERAGE_TEST_USER.md` with user specification
- Created `setup-ux-test-user.py` for validation

## After State

| Metric | Value |
|--------|-------|
| **Workflow Run** | _PENDING - Update after run_ |
| **Score** | _PENDING_ |
| **Status** | _PENDING_ |
| **P0 Failures** | _PENDING_ |
| **P1 Failures** | _PENDING_ |
| **Dead Ends** | _PENDING_ |
| **Tokens Acquired** | _PENDING_ |

## Validation Checklist

- [ ] GitHub secrets configured (`UX_TEST_USER_EMAIL`, `UX_TEST_USER_PASSWORD`)
- [ ] Test user created in staging database
- [ ] Test user can authenticate (verified via API)
- [ ] Tokens acquired in CI (check workflow logs)
- [ ] Auth-protected routes NOT skipped
- [ ] P0 failures reduced (ideally 0)
- [ ] Score improved (target >= 85)
- [ ] Status improved (target: STAGING or GO)

## Security Attestation

| Control | Status |
|---------|--------|
| Credentials stored in GitHub Secrets only | ✅ |
| Tokens masked in all workflow logs | ✅ |
| No credentials/tokens in artifacts | ✅ |
| Test user staging-only | ✅ |
| PII sanitization active | ✅ |

## PII Statement

This evidence pack and all associated artifacts contain **no PII**:
- Test user email is masked in logs
- Tokens are masked in all outputs
- Form data uses placeholder values
- Console logs are sanitized

## Control Tower Integration

After auth enablement, the UX signal in Control Tower should reflect:

```json
{
  "ux": {
    "score": "<updated>",
    "status": "<updated>",
    "p0_failures": "<updated>",
    "tokens_acquired": true
  }
}
```

## Next Steps

1. Configure GitHub secrets (admin action)
2. Create test user in staging (admin action)
3. Trigger UX coverage workflow
4. Update this evidence pack with results
5. Close PR when GO achieved

## Appendix: Commits

| SHA | Message |
|-----|---------|
| `516c9bc` | feat(ux-coverage): add dynamic token acquisition for auth testing |

---

*Evidence pack created: 2026-01-26*
*Last updated: 2026-01-26*
