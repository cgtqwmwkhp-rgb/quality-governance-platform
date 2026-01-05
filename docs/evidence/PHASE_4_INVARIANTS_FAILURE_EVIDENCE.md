# Phase 4: Invariants Failure Demonstration - Evidence

## Objective

Prove that the OpenAPI contract invariants validation gate is truly BLOCKING by deliberately violating an invariant and confirming CI fails.

## Test Execution

### Step 1: Introduce Deliberate Invariant Violation

**Commit:** 39e0592 - "[TEST] Break invariant to prove CI gate is blocking"

**Change Made:**
Removed the `total` field from `ComplaintListResponse` schema in `docs/contracts/openapi.json`.

**Local Validation Result:**
```
=== OpenAPI Contract Validation ===
❌ Paginated response schema errors (1):
  - Schema ComplaintListResponse: Missing paginated response fields: {'total'}
❌ Contract validation failed with 1 errors
```

### Step 2: Push and Monitor CI

**PR:** #17 - Stage 3.0.1: OpenAPI Gate Verification + Schema Contract Consistency
**CI Run URL:** https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/20712213515/job/59455130538?pr=17

## CI Results

### Job Status: ❌ FAILED

**Duration:** 38 seconds

### Step Execution Summary

| Step | Status | Duration |
|------|--------|----------|
| Set up job | ✅ | 1s |
| Checkout code | ✅ | 8s |
| Set up Python 3.11 | ✅ | 1s |
| Install dependencies | ✅ | 28s |
| Prove determinism (BLOCKING) | ✅ | 4s |
| **Validate contract invariants (BLOCKING)** | ❌ **FAILED** | 9s |
| **Check for contract drift (BLOCKING)** | ❌ **FAILED** | 9s |
| Upload drift artifacts | ✅ | 1s |

### Error Annotations

**2 errors detected:**

1. ❌ **Check for contract drift (BLOCKING)**
   - Message: "Process completed with exit code 1"

2. ❌ **Check for contract drift (BLOCKING)**
   - Message: "OpenAPI drift detected. Run python3.11 scripts/generate_openapi.py and commit docs/contracts/openapi.json"

**Note:** Both the invariants check and drift check failed. The invariants check failed because the schema violated the pagination response contract (missing `total` field). The drift check also failed because the manually edited schema doesn't match what the generator produces.

## Gate 4 Status: PASSED ✅

**The contract invariants gate is TRULY BLOCKING.**

The CI failed when an invariant was violated (missing required field in paginated response schema). This proves that:

1. The gate detects invariant violations accurately
2. The gate fails the CI build (blocking)
3. The validation script correctly enforces pagination response schema requirements

## Next Steps

Revert the broken schema by regenerating it properly to restore CI to green status.
