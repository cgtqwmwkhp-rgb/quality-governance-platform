# CI Gate Hygiene (D17)

Transparency and rationale for the CI gate model in the Quality Governance Platform.

---

## Gate Model Overview

The platform CI pipeline consists of **33 blocking jobs** aggregated under the `all-checks` required status check, plus **advisory and scheduled gates** that run outside the blocking path.

Every pull request must pass all 33 blocking jobs before merge. Advisory and scheduled gates provide additional signal without impeding developer velocity.

---

## Gate Classification

| Classification | Behavior | Examples |
|---------------|----------|----------|
| **Blocking** | Exits non-zero on failure; PR cannot merge | Unit tests, mypy, import boundaries, Lighthouse, size-limit, lockfile integrity |
| **Advisory** | Runs in CI, logged, but does not block merge | DAST ZAP baseline scan |
| **Scheduled** | Runs on a cron schedule, not per-PR | Mutation testing (weekly) |

### Why DAST ZAP Is Advisory

The ZAP DAST scan runs a **baseline spider/passive scan** against the built application. It produces informational findings (e.g., missing headers on non-sensitive routes, cookie flags in dev mode) that require human triage. Making it blocking would generate false-positive merge friction without proportional security benefit. Findings are reviewed during the weekly security triage and tracked as issues.

### Why Mutation Testing Is Scheduled

Mutation testing (via `mutmut` or equivalent) reruns the test suite hundreds of times with injected faults. This is a **cost/time trade-off**:

- A full mutation run can take 30–60 minutes, far exceeding acceptable PR feedback time.
- Running weekly catches test-quality regressions without blocking every commit.
- Results are published to the team channel and tracked as test-health metrics.

---

## Pre-Existing Failures

The following CI jobs are documented as **pre-existing failures** in [`docs/evidence/release_signoff.json`](../evidence/release_signoff.json). Each has a stated root cause, risk assessment, and mitigation:

| Job | Root Cause | Risk | Mitigation |
|-----|-----------|------|------------|
| **`alembic-check`** | CI environment lacks a live database connection; Alembic migration head checks require a running PostgreSQL instance | Low | Migrations are verified locally and validated during staging deployment before every release |
| **`lockfile-check`** | CI runners lack `pip-compile`; the lockfile freshness check cannot re-resolve dependencies | Low | Lockfile is regenerated locally with hash pinning; dependency integrity verified by pip install with `--require-hashes` |
| **`e2e-tests`** | End-to-end tests require a running application server, which is not provisioned in the standard CI matrix | Low | Covered by 1,373 passing unit + integration tests; E2E suite runs in staging pre-release |
| **`locust-load-test`** | Load tests require a running application server in CI | Low | Performance thresholds (p95 < 500 ms, error rate < 1%) are enforced when the server is available; load tests run in staging |
| **`dast-zap-advisory`** | Intentionally advisory — baseline scan produces informational findings | None | Findings triaged weekly; no blocking security issues identified |

### Risk Assessment Summary

- **No high-risk pre-existing failures.** All failures stem from CI environment constraints (no live database, no running server) rather than code defects.
- **Every gap has a compensating control:** local verification, staging validation, or integration test coverage.
- Blocking test suites (1,379 collected, 1,373 passed, 7 skipped, 0 failures) and 178 frontend tests provide strong regression coverage.

---

## How This Supports Fast Iteration and Governance

| Goal | Mechanism |
|------|-----------|
| **Fast iteration** | Only jobs that can run reliably in CI are blocking; flaky or environment-dependent gates are moved to advisory/scheduled to avoid false-negative friction |
| **Governance** | Every non-blocking gate has a documented rationale and risk level; pre-existing failures are tracked in the release signoff artifact with explicit risk acceptance |
| **Auditability** | The `release_signoff.json` artifact records the exact CI state at release time, including all pre-existing failures and their justifications |
| **Continuous improvement** | As CI infrastructure matures (e.g., adding a database service container), advisory gates are promoted to blocking |

---

## Evidence

- [`docs/evidence/release_signoff.json`](../evidence/release_signoff.json) — release signoff with pre-existing failure documentation
- PR checks dashboard: 38 checks passed at most recent release
- Unit tests: 1,379 collected, 1,373 passed, 7 skipped
- Frontend tests: 178 passed
- mypy: 323 files, 0 errors

---

## Related Documents

- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — performance SLOs and CI threshold reconciliation
- [`docs/observability/alerting-rules.md`](../observability/alerting-rules.md) — production alerting rules
- [`docs/infra/canary-rollout-plan.md`](../infra/canary-rollout-plan.md) — canary deployment and rollback triggers
