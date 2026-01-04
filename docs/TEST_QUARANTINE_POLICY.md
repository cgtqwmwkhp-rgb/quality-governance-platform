# Integration Test Quarantine Policy

## Purpose

This document defines the policy for quarantining integration tests that cannot be made green due to missing application features or known issues, while maintaining strict merge safety for the non-quarantined test suite.

## Quarantine Criteria

A test may be quarantined **only** if all of the following conditions are met:

1. The test is validating a feature that is **not yet implemented** in the application
2. The test failure is **not** due to a bug in existing functionality
3. The test is **properly written** and would pass once the feature is implemented
4. A **tracked GitHub issue** has been created and linked in this document
5. The quarantine entry includes: test name, file, reason, issue link, owner, quarantine date, and expiry date
6. The test is marked with `@pytest.mark.skip(reason="Quarantined - [issue description], see docs/TEST_QUARANTINE_POLICY.md")`

**Any test marked as skipped without a corresponding entry in this policy document will cause CI to fail.**

## Current Quarantined Tests

**None** - All integration tests are currently passing.

## Merge Gate Policy

**The merge gate remains strict for all non-quarantined integration tests.** All tests in the `tests/integration/` directory that are not explicitly listed in this document **MUST** pass before a pull request can be merged.

Quarantined tests are marked with `@pytest.mark.skip(reason="Quarantined - see TEST_QUARANTINE_POLICY.md")` and do not block merges.

## Enforcement

The CI pipeline includes a quarantine validation step that:

1. Scans all integration tests for `@pytest.mark.skip` decorators
2. Extracts the test names from skipped tests
3. Verifies each skipped test has a corresponding entry in this policy document
4. Fails the build if any skipped test is not documented here

This prevents silent expansion of the quarantine list and ensures all skipped tests are tracked, owned, and time-boxed.

## Review Process

This quarantine policy must be reviewed every 30 days. Tests that remain quarantined beyond their expiry date must either:

1. Have the missing feature implemented and be un-quarantined
2. Be removed from the test suite if the feature is no longer planned
3. Have their expiry date extended with explicit justification and updated issue status

**Last Reviewed**: 2026-01-04
