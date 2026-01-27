# Actions Module Rollback Runbook

## Overview

This runbook documents the rollback procedures for the Actions module. **Critical: Rollback must never reintroduce mock data into production.**

## Rollback Scenarios

### Scenario 1: API Backend Issue (Recommended)

If the Actions PATCH endpoint or API integration is causing issues:

**Option A: Disable PATCH endpoint (safest)**
```bash
# In src/api/routes/actions.py, comment out the PATCH endpoint
# This keeps list/create working but disables updates
```

**Option B: Feature flag the update functionality**
```typescript
// In frontend, disable update button via feature flag
const ACTIONS_UPDATE_ENABLED = false;
```

### Scenario 2: Full Module Rollback

If complete rollback is required:

1. **Revert to previous API-backed commit**
   - Find the last known good commit before PR #99
   - Ensure the rollback target is still API-backed (not mock)
   
2. **NEVER acceptable:**
   - Reintroducing `MOCK_ACTIONS` array
   - Reintroducing `setTimeout` simulations
   - Returning to hardcoded data

### Scenario 3: Frontend-Only Rollback

If only the frontend is problematic:

1. Revert frontend changes but keep backend PATCH endpoint
2. Disable the "New Action" button until fix is ready
3. Use CSS/JS to hide problematic UI elements

## Rollback Commands

```bash
# Revert a specific commit
git revert <commit-sha>

# Revert to a specific point (creates new commit)
git revert --no-commit HEAD~N..HEAD
git commit -m "Revert: rollback Actions module to stable state"

# VERIFY after rollback:
# 1. No MOCK_ patterns in Actions.tsx
# 2. No setTimeout simulations
# 3. API calls still present (actionsApi.list, actionsApi.create)
```

## Post-Rollback Verification

Run the Mock Data Eradication Gate to ensure no mocks were reintroduced:

```bash
python3 scripts/check_mock_data.py --repo-root .
# Expected: [PASS] No mock data patterns detected in scoped files.
```

## Escalation

If rollback is required and all options introduce mock data:

1. **STOP** - Do not deploy mock data to production
2. **Escalate** to Principal Engineer
3. **Option**: Disable entire module via feature flag until proper fix

## Evidence Required After Rollback

1. Mock gate output showing PASS
2. CI run showing all checks green
3. Screenshot of /actions page loading from API

---

*Last Updated: 2026-01-27*
*PR #99: feat(pr1): API-back Actions module + Mock Data Eradication Gate*
