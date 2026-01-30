# ADR-0003: SWA Deployment Gating Exception for Tooling PRs

**Status**: Accepted  
**Date**: 2026-01-30  
**Decision Makers**: Release Governance Lead  
**Supersedes**: N/A

---

## Context

Azure Static Web Apps (SWA) has a limit on staging/preview environments (3-10 depending on plan). PRs create preview environments, and when the limit is reached, subsequent deployments fail with:

```
BadRequest: This Static Web App already has the maximum number of staging environments
```

This blocks CI for PRs that don't even modify frontend code.

## Decision

**The "Build and Deploy Job" (SWA preview deployment) is NON-BLOCKING for PRs that do not modify frontend source files.**

### Implementation

1. **Path Filter**: SWA deployment only triggers on changes to:
   - `frontend/src/**`
   - `frontend/public/**`
   - `frontend/index.html`
   - `frontend/package.json`
   - `frontend/vite.config.ts`

2. **Explicit Skip**: The `check_changes` job detects frontend changes; if none, deployment is skipped.

3. **Environment Limit**: When limit is reached, non-frontend PRs may show "Build and Deploy Job: fail" but this is acceptable if:
   - All quality gates pass
   - No frontend files were modified

### Compensating Controls

| Control | Enforcement Point | Blocking? |
|---------|------------------|-----------|
| Unit Tests | CI | ✅ Yes |
| Integration Tests | CI | ✅ Yes |
| Security Scans | CI | ✅ Yes |
| Smoke Tests (CRITICAL) | CI | ✅ Yes |
| UAT Tests | CI | ✅ Yes |
| E2E Tests | CI | ✅ Yes |
| Frontend Change Detection | SWA Workflow | ✅ Yes (skips if no changes) |
| Production Deployment | Release workflow | ✅ Yes (always deploys) |

## Consequences

### Positive
- Backend/tooling PRs can merge without waiting for SWA environment capacity
- Reduces unnecessary preview environment creation
- Faster CI for non-frontend changes

### Negative
- "Build and Deploy Job: fail" may appear on some PRs (cosmetic)
- Requires documentation for team awareness

### Risks Mitigated
- Production deployment is always enforced on main branch
- All quality gates remain blocking
- Frontend changes are detected and require successful deployment

## Compliance

This exception does NOT weaken:
- ADR-0001: Schema migration requirements
- ADR-0002: Fail-fast configuration
- CI security covenants

---

**Document Owner**: Platform Team  
**Review Cycle**: Quarterly
