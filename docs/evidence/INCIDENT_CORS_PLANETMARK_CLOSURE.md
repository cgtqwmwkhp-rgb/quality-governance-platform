# Incident Report: INC-2026-01-30-CORS

> **Template Version**: 1.0  
> **Conforms To**: `docs/evidence/INCIDENT_TEMPLATE.md`  
> **Status**: ✅ CLOSED

---

## Quick Reference

| Field | Value |
|-------|-------|
| **Incident ID** | `INC-2026-01-30-CORS` |
| **Severity** | SEV2 |
| **Status** | CLOSED |
| **Opened** | 2026-01-28T20:41:51Z |
| **Closed** | 2026-01-30T13:21:47Z |
| **Duration** | ~40 hours (detection to closure) |
| **Owner** | Release Governance SRE |

---

## 1. Impact

### Customer Impact
- **Users Affected**: All frontend users attempting to use the portal
- **Features Impacted**: All API calls from frontend to backend
- **Error Observed**: CORS errors in browser console, API calls blocked

### Business Impact
- All portal functionality degraded for users on `app-qgp-prod.azurestaticapps.net` domain
- Duration of impact: ~40 hours from incomplete PR #113 merge to full fix

---

## 2. Timeline

| Time (UTC) | Event |
|------------|-------|
| 2026-01-28T20:41:51Z | PR #113 merged - CORS fix (incomplete) |
| 2026-01-28T20:57:50Z | Commit `5e87d91` deployed to production |
| 2026-01-28T21:00:00Z | Deploy run 21455022182 completed |
| 2026-01-30T12:21:48Z | Runtime validation detected CORS still failing |
| 2026-01-30T12:22:00Z | Root cause identified: missing origin in allowlist |
| 2026-01-30T12:27:00Z | PR #115 created with fix + runtime smoke gate |
| 2026-01-30T12:37:59Z | PR #115 merged (SHA `f216f43`) |
| 2026-01-30T12:44:21Z | Production deploy run 21516248071 started |
| 2026-01-30T12:54:27Z | Runtime smoke gate passed |
| 2026-01-30T12:55:42Z | CORS verified working for both origins |
| 2026-01-30T13:01:11Z | PR #116 merged - PlanetMark 500 fix (SHA `d9ce118`) |
| 2026-01-30T13:21:47Z | All checks pass, incident closed |

---

## 3. Root Cause

### Summary
PR #113 CORS fix was incomplete. The production frontend origin `app-qgp-prod.azurestaticapps.net` was not included in the explicit CORS allowlist, and did not match the regex pattern which required a `.NUMBER.` segment.

### Technical Details
The CORS configuration in `src/core/config.py` and `src/api/exceptions.py` only included:
- `https://purple-water-03205fa03.6.azurestaticapps.net` (auto-generated Azure SWA URL)
- Localhost origins for development

The regex pattern `^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$` requires a `.NUMBER.` segment (e.g., `.6.`), which the production URL `app-qgp-prod.azurestaticapps.net` lacks.

### Secondary Issue: PlanetMark Dashboard 500
The PlanetMark dashboard endpoint returned HTTP 500 instead of 200 due to missing database table (migrations not applied). This was masked by the smoke gate only warning on 500, not failing.

### Contributing Factors
- [x] Missing tests (no test for production origin)
- [x] Configuration drift (auto-generated vs custom domain mismatch)
- [x] Smoke gate allowed 500 as warning, not failure

---

## 4. Fix

### Immediate Mitigation
None available - required code change.

### Permanent Fix

| PR | SHA | Description |
|----|-----|-------------|
| #115 | `f216f43043d24fb9fd0d6d759497b284b49fd140` | Add `app-qgp-prod.azurestaticapps.net` to CORS allowlist + runtime smoke gate |
| #116 | `d9ce118310110a62bf853a8f7cf5b38de6370fce` | Return setup_required instead of 500 for PlanetMark |

### Files Modified

| File | Change |
|------|--------|
| `src/core/config.py` | Added `https://app-qgp-prod.azurestaticapps.net` to `cors_origins` |
| `src/api/exceptions.py` | Added same origin to `CORS_ALLOWED_ORIGINS` |
| `.github/workflows/deploy-production.yml` | Added post-deploy runtime smoke gate |
| `src/api/routes/planet_mark.py` | Return setup_required (200) instead of 500 |

---

## 5. Verification

### Pre-deploy Verification
| Check | Result | Evidence |
|-------|--------|----------|
| CI passes (PR #115) | ✅ | 23/23 checks passed |
| CI passes (PR #116) | ✅ | All checks passed |
| CORS origins verified in code | ✅ | Both origins in allowlist |

### Post-deploy Verification
| Check | Result | Evidence |
|-------|--------|----------|
| Smoke gate passes | ✅ | Deploy Run 21516248071 |
| Build SHA verified | ✅ | `d9ce118` matches |
| CORS OPTIONS (purple-water) | ✅ | HTTP 200, ACAO matches |
| CORS OPTIONS (app-qgp-prod) | ✅ | HTTP 200, ACAO matches |
| CORS GET credentials | ✅ | `access-control-allow-credentials: true` |
| UVDB sections | ✅ | HTTP 200 |
| PlanetMark dashboard | ✅ | HTTP 200 with setup_required |

### CORS Proof Table

| Endpoint | Origin | Status | ACAO Header | Pass/Fail |
|----------|--------|--------|-------------|-----------|
| `/api/v1/meta/version` | purple-water-...6 | 200 | ✅ Matches | ✅ PASS |
| `/api/v1/meta/version` | app-qgp-prod | 200 | ✅ Matches | ✅ PASS |

---

## 6. Prevention

### Immediate Actions (Completed)
- [x] Add runtime smoke gate to production deploy — Owner: SRE — Done: 2026-01-30
- [x] Make PlanetMark return 200 with setup_required — Owner: SRE — Done: 2026-01-30

### Long-term Improvements (This PR)
- [x] Harden smoke gate: 5xx on critical endpoints = FAIL
- [x] Add expiring allowlist mechanism for temporary overrides
- [x] Standardize setup_required response schema
- [x] Create incident postmortem template

---

## 7. Artifacts

### Deploy Run IDs

| Environment | Run ID | Status | Link |
|-------------|--------|--------|------|
| Staging (PR #115) | 21516079139 | ✅ success | [Link](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/21516079139) |
| Production (PR #115) | 21516248071 | ✅ success | [Link](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/21516248071) |
| Staging (PR #116) | 21516699261 | ✅ success | [Link](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/21516699261) |
| Production (PR #116) | 21516967756 | ✅ success | [Link](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/21516967756) |

### Commit SHAs

| Commit | Description |
|--------|-------------|
| `f216f43` | CORS fix + runtime smoke gate (PR #115) |
| `d9ce118` | PlanetMark setup_required response (PR #116) |

---

## 8. Rollback Plan

### If Issue Recurs
1. Revert commit `d9ce118` with `git revert d9ce118`
2. Revert commit `f216f43` with `git revert f216f43`
3. Push to main via PR
4. Deploy will auto-trigger
5. Verify smoke gate passes

### Emergency Bypass
If smoke gate is failing but deploy is critical:
1. Add temporary allowlist entry to `docs/evidence/runtime_smoke_allowlist.json`
2. Set expiry_date to max 7 days
3. Create follow-up issue immediately

---

## 9. Lessons Learned

### What Went Well
- Runtime smoke gate caught the issue (after being implemented)
- Quick triage and fix once identified
- Evidence-led approach worked

### What Could Be Improved
- PR #113 should have been tested with both production origins
- Smoke gate should have failed on 500, not warned
- Need automated test for CORS with all production origins

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-30 | Release Governance SRE | Initial creation |
| 1.1 | 2026-01-30 | Release Governance SRE | Conformed to incident template |

---

**Review Required By**: Release Governance Lead  
**Approved By**: _Automated via CI_  
**Date**: 2026-01-30
