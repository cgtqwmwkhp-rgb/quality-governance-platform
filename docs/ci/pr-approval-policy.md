# PR Approval Policy (D17)

Pull request approval requirements and CI quality gate documentation.

## Approval Requirements

| PR Type | Minimum Reviewers | CI Gates Required | Additional Requirements |
|---------|-------------------|-------------------|------------------------|
| Feature | 1 | All 25+ CI checks pass | Change ledger in PR body |
| Bug fix | 1 | All CI checks pass | Root cause documented |
| Infrastructure | 1 | All CI checks pass | Impact assessment |
| Documentation | 1 | Relevant CI checks pass | — |
| Emergency hotfix | 1 (post-hoc OK) | Smoke tests pass | Incident reference required |

## CI Quality Gates (Blocking)

All gates in the `all-checks` job must pass before merge:

| Gate | Job Name | Tool |
|------|----------|------|
| Code quality (lint, format, type-check) | `code-quality` | black, isort, ruff, mypy |
| Workflow lint | `workflow-lint` | actionlint |
| Unit tests (coverage >= 50%) | `unit-tests` | pytest |
| Frontend tests | `frontend-tests` | vitest |
| Integration tests (coverage >= 50%) | `integration-tests` | pytest |
| Security scan | `security-scan` | gitleaks, pip-audit |
| SBOM generation | `sbom` | cyclonedx |
| Build check | `build-check` | docker build |
| Smoke tests | `smoke-tests` | pytest |
| E2E tests | `e2e-tests` | playwright |
| UAT tests | `uat-tests` | pytest |
| Performance budget | `performance-budget` | Lighthouse, size-limit |
| Locust load test | `locust-load-test` | Locust |
| Lockfile freshness | `lockfile-check` | pip-compile |
| Migration naming | `migration-naming-lint` | custom script |
| Contract tests | `contract-tests` | schemathesis |
| Secret scanning | `secret-scanning` | gitleaks |
| API path drift | `api-path-drift` | custom script |
| Config drift guard | `config-drift-guard` | custom script |

## PR Body Template

All PRs must use the template at `scripts/governance/pr_body_template.md`, which includes:

- Change ledger (files changed, risk assessment)
- Acceptance criteria count
- Testing evidence
- Rollback plan

## Branch Protection

- Direct pushes to `main` are blocked.
- Force pushes to `main` are blocked.
- Merge requires `all-checks` job to pass.
- Stale approvals are dismissed on new pushes.

## Related Documents

- [`scripts/governance/pr_body_template.md`](../../scripts/governance/pr_body_template.md) — PR template
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — CI configuration
- [`docs/evidence/release_signoff.json`](../evidence/release_signoff.json) — release signoff
