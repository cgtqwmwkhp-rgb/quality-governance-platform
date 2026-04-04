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
| **Blocking** | Exits non-zero on failure; PR cannot merge | Unit tests, mypy, import boundaries, Lighthouse, size-limit, lockfile integrity, alembic-check |
| **Advisory** | Runs in CI, logged, but does not block merge | DAST ZAP baseline scan |
| **Scheduled** | Runs on a cron schedule, not per-PR | Mutation testing (weekly) |
| **Parallel pipeline** | Runs on same triggers via separate workflow; findings surfaced via GitHub Security tab | CodeQL SAST, Trivy container scan, Semgrep |

### Security Scanning Pipeline (`security-scan.yml`)

A separate `security-scan.yml` workflow runs on every push/PR to `main`/`develop` and weekly. It includes:

- **CodeQL SAST** — GitHub CodeQL analysis for Python and JavaScript (`sast-codeql` job, matrix strategy). Findings appear in the GitHub Security tab.
- **Semgrep SAST** — Additional SAST scanning with auto-config + custom rules (`.semgrep.yml`).
- **Bandit** — Python-specific security linting (high-severity blocking).
- **Trivy** — Container image vulnerability scanning (HIGH/CRITICAL blocking, SARIF uploaded to GitHub).
- **Gitleaks** — Secret detection across git history.
- **Safety** — Dependency vulnerability check.

This pipeline runs on the **same triggers** as `ci.yml` and provides defense-in-depth. CodeQL and Trivy findings are automatically surfaced via GitHub Advanced Security.

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

| Job | Root Cause | Risk | Status |
|-----|-----------|------|--------|
| **`alembic-check`** | Previously lacked a database service container | — | **RESOLVED** — PostgreSQL service container added to CI job; now runs `alembic upgrade head && alembic check` |
| **`lockfile-check`** | `pip-compile` hash resolution may produce minor drift from upstream releases | Low | Smart diff only fails on actual package version changes (not hash/comment drift) |
| **`e2e-tests`** | End-to-end tests require a running application server with seeded data | Low | Covered by 1,373+ passing unit + integration tests; E2E suite runs in staging pre-release |
| **`locust-load-test`** | Load tests require a running application server in CI | Low | Performance thresholds (p95 < 500 ms, error rate < 1%) enforced in staging; see `docs/slo/performance-slos.md` |
| **`dast-zap-advisory`** | Intentionally advisory — baseline scan produces informational findings | None | Findings triaged weekly; no blocking security issues identified |

### Risk Assessment Summary

- **`alembic-check` resolved** — now runs with a PostgreSQL service container, eliminating the pre-existing failure.
- **Remaining 4 items are Low/None risk.** Three stem from CI environment constraints (no running application server) rather than code defects; one is advisory by design.
- **Every gap has a compensating control:** staging validation, integration test coverage, or weekly triage.
- Blocking test suites (1,379+ collected, 0 failures) and 178+ frontend tests provide strong regression coverage.

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
