# Stage 0.6 - Phase 1: Governance Hardening

## Touched Files

- **Created**: `docs/BRANCH_PROTECTION_CHECKLIST.md` (actionable checklist for branch protection settings)
- **Created**: `scripts/validate_type_ignores.py` (type-ignore validator with ceiling enforcement)
- **Modified**: `.github/workflows/ci.yml` (added type-ignore validator step)
- **Modified**: `src/api/routes/users.py` (added issue tags to type-ignore comments)
- **Modified**: `src/api/routes/standards.py` (added issue tag to type-ignore comment)
- **Modified**: `src/services/reference_number.py` (added issue tag to type-ignore comment)
- **Verified**: `.flake8` (confirmed scope is properly limited)

## Root Cause + Fix Summary

### Branch Protection Checklist
- **Created**: Actionable checklist for configuring branch protection on `main`
- **Requirements**:
  - Require PR reviews (at least 1)
  - Require `all-checks` status check to pass
  - Disable bypass protections for admins
  - Prevent force pushes and deletions

### Type-Ignore Drift Prevention
- **Problem**: Type-ignore comments could proliferate without oversight
- **Solution**: Implemented `validate_type_ignores.py` with three rules:
  1. All type-ignores must be error-code-specific (e.g. `# type: ignore[arg-type]`)
  2. All type-ignores must include an issue ID tag (e.g. `# TYPE-IGNORE: SQLALCHEMY-001`)
  3. Total count cannot exceed ceiling (currently 5, with 4 in use)
- **Added to CI**: New step in code-quality job runs before mypy

### Flake8 Scope Validation
- **Verified**: `.flake8` configuration is properly scoped
- **Global ignores**: E501 (line length), E712 (comparison with True), E203, W503 (acceptable)
- **Scoped ignores**: F401 (unused imports) limited to:
  - `src/domain/models/*.py` (model files may have future-use imports)
  - `tests/conftest.py` (fixture file may have conditional imports)
- **Conclusion**: Safe, no tightening needed

## CI Guardrail Implementation Summary

### Quarantine Validator (Already in Place)
- **Script**: `scripts/validate_quarantine.py`
- **Runs**: Integration Tests job, before pytest
- **Checks**: All skipped integration tests must be listed in `docs/TEST_QUARANTINE_POLICY.md`
- **Fails if**: Any skipped test is not in the policy (prevents silent test suite degradation)

### Type-Ignore Validator (New)
- **Script**: `scripts/validate_type_ignores.py`
- **Runs**: Code Quality job, before mypy
- **Checks**:
  - No generic type-ignores (must be error-code-specific)
  - All type-ignores have issue ID tags
  - Total count ≤ MAX_TYPE_IGNORES (currently 5)
- **Fails if**: Any rule is violated (prevents type-ignore proliferation)

## Evidence

### GitHub Actions Run URL
https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/20693243570

### Type-Ignore Validator Output (from CI logs)
```
🔍 Validating type-ignore comments...
📊 Maximum allowed type-ignores: 5

✅ Valid type-ignores (with issue tags): 4
   - .../src/api/routes/users.py:105
   - .../src/api/routes/users.py:158
   - .../src/api/routes/standards.py:210
   - .../src/services/reference_number.py:32

✅ All type-ignore validations passed!
   Total type-ignores: 4/5
```

### Quarantine Validator Output (from CI logs)
```
scripts/validate_quarantine.py
✅ Quarantine policy is valid. 1 quarantined test found, 1 allowed.
```

### All CI Jobs Status
| Job                 | Status  | Duration |
| ------------------- | ------- | -------- |
| Code Quality        | ✅ Pass | 45s      |
| Security Scan       | ✅ Pass | 32s      |
| Build Check         | ✅ Pass | 27s      |
| Integration Tests   | ✅ Pass | 1m 10s   |
| Unit Tests          | ✅ Pass | 41s      |
| All Checks Passed   | ✅ Pass | 4s       |

## Flake8 Scoping Outcome

**Status**: ✅ Confirmed Safe

The `.flake8` configuration is properly scoped:
- Global ignores (E501, E712, E203, W503) are acceptable for code style consistency
- F401 (unused imports) is scoped ONLY to:
  - `src/domain/models/*.py` (model files)
  - `tests/conftest.py` (test fixtures)
- No tightening required

## Gate 1 Status: ✅ MET

**Confirmation**: All Phase 1 requirements are met:
- ✅ Branch protection checklist provided (actionable)
- ✅ CI guardrail implementation summary provided (quarantine + type-ignore validators)
- ✅ Evidence provided (GitHub Actions run URL + log excerpts showing both validators executed successfully)
- ✅ Flake8 scoping confirmed safe (no changes needed)

**Next**: Proceed to Phase 2 (Quarantine Burn-down)
