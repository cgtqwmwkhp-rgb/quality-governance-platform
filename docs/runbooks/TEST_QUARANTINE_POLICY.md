# Test Quarantine Policy

## Purpose
This document defines the governance process for temporarily disabling (quarantining) tests in the Quality Governance Platform CI pipeline. The goal is to maintain test quality and prevent permanent test debt while allowing development to continue when tests are flaky or blocked on external factors.

## Key Principles

1. **No Silent Skips**: Tests must never be skipped without a tracked issue and documented reason.
2. **Time-Bounded**: Every quarantined test must have a target re-enable date.
3. **Ownership**: Every quarantined test must have an assigned owner responsible for resolution.
4. **Visibility**: CI must report all skipped/quarantined tests prominently.
5. **Escalation**: Quarantined tests older than 14 days require escalation.

## Allowed Quarantine Reasons

| Reason Code | Description | Max Duration |
|-------------|-------------|--------------|
| `FLAKY` | Test passes locally but fails intermittently in CI | 7 days |
| `EXTERNAL_DEP` | Test depends on external service that is temporarily unavailable | 14 days |
| `INFRA_ISSUE` | CI infrastructure issue (e.g., container, network) | 7 days |
| `BLOCKED_BY_BUG` | Test blocked by a known bug being fixed | Until bug is fixed (max 30 days) |
| `REFACTOR_NEEDED` | Test needs refactoring due to architectural changes | 14 days |
| `ENV_SPECIFIC` | Test only works in specific environment (e.g., local but not CI) | 7 days |

## Required Quarantine Annotation

Every quarantined test **MUST** use the following format:

### Python (pytest)

```python
@pytest.mark.skip(reason="QUARANTINE: [ISSUE-ID] [REASON_CODE] - [description] | Owner: [email] | Target: [YYYY-MM-DD]")
def test_example():
    ...
```

**Example:**
```python
@pytest.mark.skip(
    reason="QUARANTINE: GH-1234 FLAKY - Intermittent timeout on Postgres connection pool | Owner: dev@example.com | Target: 2026-02-01"
)
def test_database_connection():
    ...
```

### Alternative: Using pytest marks

```python
@pytest.mark.quarantine(
    issue_id="GH-1234",
    reason_code="FLAKY",
    description="Intermittent timeout on Postgres connection pool",
    owner="dev@example.com",
    target_date="2026-02-01"
)
def test_database_connection():
    ...
```

## Quarantine Workflow

### 1. Quarantining a Test

1. **Create Issue**: Open a GitHub issue describing the failure with:
   - Test name and file path
   - Failure evidence (stack trace, CI run link)
   - Reproduction steps (if known)
   - Proposed fix or investigation plan

2. **Add Annotation**: Add the quarantine skip with all required fields.

3. **Update CI Config**: Ensure the test is excluded from required checks if needed.

4. **Notify Team**: Post in the team channel about the quarantine.

### 2. Monitoring Quarantined Tests

CI pipeline **MUST**:
- Print a summary of all skipped tests at the end of each run
- Fail if any quarantine annotation is missing required fields
- Warn if any quarantine has exceeded its target date

### 3. Re-enabling Tests

1. **Fix the Issue**: Address the root cause.
2. **Run Locally**: Verify the test passes locally (multiple runs for flaky tests).
3. **Remove Annotation**: Delete the quarantine marker.
4. **Close Issue**: Update and close the tracking issue.
5. **Verify CI**: Ensure the test passes in CI for at least 3 consecutive runs.

## CI Reporting Requirements

The CI pipeline must output the following at the end of test runs:

```
========== Test Quarantine Report ==========
Total Tests:     150
Passed:          145
Failed:          0
Skipped:         5
  - Quarantined: 3
  - Other Skip:  2

Quarantined Tests:
  1. tests/integration/test_db.py::test_pool_exhaustion
     Issue: GH-1234 | Reason: FLAKY | Owner: dev@example.com | Target: 2026-02-01

  2. tests/e2e/test_auth.py::test_oauth_flow
     Issue: GH-1235 | Reason: EXTERNAL_DEP | Owner: auth@example.com | Target: 2026-02-05

  3. tests/unit/test_cache.py::test_redis_timeout
     Issue: GH-1236 | Reason: INFRA_ISSUE | Owner: infra@example.com | Target: 2026-01-30

WARNINGS:
  - test_cache.py::test_redis_timeout: Target date EXCEEDED (2026-01-30)
============================================
```

## Enforcement

### Pre-commit Hook

```bash
# Check for bare skips without quarantine annotation
grep -r "@pytest.mark.skip" tests/ | grep -v "QUARANTINE:" && \
  echo "ERROR: Found skip markers without QUARANTINE annotation" && exit 1
```

### CI Gate

The `validate_quarantine_policy` CI step must:
1. Parse all test files for skip markers
2. Validate each has required fields (issue_id, reason_code, owner, target_date)
3. Report any violations as warnings (not failures, to avoid blocking PRs)
4. Fail if a test has been quarantined for > 30 days

## Rollback Policy

**Important**: The rollback plan for a failing test suite is:
1. **Fix the bug** causing the test failure, OR
2. **Quarantine the test** with proper annotation (not "re-add skip markers")

"Re-add skip markers" is **NOT** an acceptable rollback strategy as it bypasses governance.

## Metrics

Track the following metrics monthly:
- Total quarantined tests
- Average quarantine duration
- Tests exceeding target date
- Tests re-enabled
- Net change in quarantine count

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-27 | Platform Team | Initial policy |
