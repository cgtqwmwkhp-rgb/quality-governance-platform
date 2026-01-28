# Test Quarantine Policy

## Purpose

This document defines the governance framework for quarantining tests in the Quality Governance Platform. It ensures that:
1. Skipped tests are tracked, owned, and time-boxed
2. Test coverage does not silently degrade
3. CI provides visibility into quarantine status
4. No plain `@pytest.mark.skip` is allowed without proper documentation

## Policy Scope

This policy applies to:
- All test files in `tests/` directory
- All pytest skip markers
- All xfail markers with `run=False`

## Quarantine Requirements

### Required Fields

Every quarantined test MUST have:

| Field | Description | Example |
|-------|-------------|---------|
| `issue_id` | GitHub issue tracking the fix | `GOVPLAT-001` |
| `owner` | Team or person responsible | `platform-team` |
| `expiry_date` | Date by which test must be fixed or reviewed | `2026-02-21` |
| `reason` | Clear explanation of why quarantined | `Phase 3/4 features not implemented` |
| `re_enable_criteria` | What must happen to un-quarantine | `Complete Phase 3 implementation` |

### Skip Marker Format

```python
@pytest.mark.skip(
    reason="QUARANTINED [GOVPLAT-001]: Brief reason. "
           "Owner: platform-team. Expiry: 2026-02-21. "
           "See docs/runbooks/TEST_QUARANTINE_POLICY.md"
)
def test_feature():
    pass
```

### Enforcement

1. **CI Validation**: `scripts/validate_quarantine.py` runs on every PR
2. **Expiry Enforcement**: Expired quarantines fail CI
3. **Budget Control**: Quarantine count cannot exceed defined limit
4. **Reporting**: CI summary includes quarantine metrics

## Allowed Quarantine Reasons

| Reason | Max Duration | Approval Required |
|--------|--------------|-------------------|
| Feature not implemented | 30 days | Team Lead |
| Known bug with fix in progress | 14 days | None |
| External dependency issue | 30 days | Architect |
| Flaky test under investigation | 7 days | None |
| Environment-specific issue | 30 days | SRE Lead |

## Prohibited Actions

❌ Plain `@pytest.mark.skip` without issue ID
❌ Commenting out tests instead of proper skip
❌ Infinite quarantine without expiry date
❌ Quarantine without updating this policy
❌ Increasing quarantine budget without explicit approval

## CI Reporting

### Summary Output

CI prints the following summary after test runs:

```
=== TEST QUARANTINE REPORT ===
Quarantine Policy: VALID
Expired: 0
Within Budget: 6/6 files

Quarantined Tests:
  - GOVPLAT-001: Phase 3/4 features (3 files, expires 2026-02-21)
  - GOVPLAT-002: API contract mismatch (3 files, expires 2026-02-21)

Test Results:
  Passed: 150
  Failed: 0
  Skipped: 6 (all quarantined with valid policy)
===========================
```

### Metrics Tracked

- `quarantine_count`: Number of quarantined test files
- `expired_count`: Quarantines past expiry date
- `days_until_expiry`: Days until next expiry
- `quarantine_coverage_percent`: % of tests that are quarantined

## Review Process

### Monthly Review

1. Review all quarantined tests
2. For each quarantine:
   - Is the underlying issue still valid?
   - Is there progress on the fix?
   - Should the expiry be extended or test removed?
3. Update `last_audit_date` in QUARANTINE_POLICY.yaml

### On Expiry

When a quarantine expires:
1. CI fails with explicit message
2. Options:
   - Fix the underlying issue and un-quarantine
   - Remove the test if feature is no longer planned
   - Request extension with updated issue status

## Rollback Policy

### Prohibited Rollback Actions

The following rollback strategies are **STRICTLY PROHIBITED**:

| ❌ Prohibited | Reason |
|---------------|--------|
| Re-add skip markers without policy entry | Any skip MUST have corresponding QUARANTINE_POLICY.yaml entry |
| Revert async correctness fixes | Reintroduces known runtime bugs (AsyncSession.query) |
| Delete tests as rollback | Tests are guardrails; removing them weakens safety |
| Comment out test assertions | Same as deleting - hides failures |
| Weaken CI gates | Undermines entire governance framework |
| Feature-flag the async harness | The session-scoped event loop harness is the blessed standard |
| Disable or bypass async_client fixture | Required for all async API tests |

### Emergency Re-Quarantine Process

If tests MUST be temporarily disabled:

1. **Create QUARANTINE_POLICY.yaml entry FIRST** with:
   - `issue_id`: New tracking ID (e.g., `EMERGENCY-001`)
   - `owner`: Person responsible
   - `expiry_date`: Max 7 days for emergencies
   - `reason`: Clear explanation
   - `approved_override: true` (required to increase quarantine count)

2. **Then add skip marker** referencing the issue:
   ```python
   pytestmark = pytest.mark.skip(
       reason="QUARANTINED [EMERGENCY-001]: Brief reason. Owner: name. Expiry: YYYY-MM-DD"
   )
   ```

3. **CI will fail** if skip added without policy entry

### Safe Rollback Strategies

If issues arise after a deployment, use these **APPROVED** strategies:

| ✅ Approved | When to Use | Example |
|-------------|-------------|---------|
| Fix forward | Always preferred | Fix the bug, don't revert |
| Revert ordering/pagination only | Non-critical regressions | Remove `order_by` change if causing perf issues |
| Feature-flag UI consumption | Unstable endpoints | Add `ENABLE_PLANETMARK_API=false` env var |
| Return controlled maintenance state | Endpoint unstable | Return `{"status": "maintenance", "retry_after": 300}` |
| Add circuit breaker | Intermittent failures | Fail gracefully instead of error |

### Runtime Bug Protection

**NEVER revert fixes for these known runtime bugs:**

| Bug ID | Description | Affected Files | Fix Status |
|--------|-------------|----------------|------------|
| ASYNC-001 | `db.query()` with AsyncSession causes AttributeError | `planet_mark.py`, `uvdb.py` | ✅ Fixed in PR#103 |

Reverting these fixes would cause immediate production failures:
```
AttributeError: 'AsyncSession' object has no attribute 'query'
```

### Escalation Path

If you believe a rollback is necessary:

1. **Do not self-approve** - get explicit sign-off
2. Escalate to Platform Architect
3. Document the business justification
4. Create a tracking issue for the re-fix
5. Set a hard deadline (max 24 hours) for restoring the fix

## Contacts

- **Policy Owner**: QA Lead
- **Enforcement**: DevOps Team
- **Exceptions**: Platform Architect

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-01-27 | 2.1 | Platform Team | Added safe rollback policy, runtime bug protection |
| 2026-01-27 | 2.0 | Platform Team | Added CI reporting, enhanced governance |
| 2026-01-21 | 1.0 | Platform Team | Initial policy |
