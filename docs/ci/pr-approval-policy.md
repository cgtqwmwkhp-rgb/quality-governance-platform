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
| Code quality (lint, format, type-check) | `code-quality` | black, isort, flake8, mypy, validate_type_ignores |
| Workflow lint | `workflow-lint` | actionlint |
| Unit tests (coverage >= 48%) | `unit-tests` | pytest (`--cov-fail-under=48`) |
| Frontend tests | `frontend-tests` | vitest, ESLint, jsx-a11y, i18n-check |
| Integration tests (coverage >= 48%) | `integration-tests` | pytest (`--cov-fail-under=48`) |
| Security scan | `security-scan` | bandit, pip-audit, waiver validation |
| SBOM generation | `sbom` | cyclonedx-bom |
| Build check | `build-check` | Python import check (`from src.main import app`) |
| Smoke tests | `smoke-tests` | pytest |
| Smoke gate selftest | `smoke-gate-selftest` | custom script |
| E2E tests | `e2e-tests` | playwright |
| UAT tests | `uat-tests` | pytest |
| Performance budget | `performance-budget` | Lighthouse, size-limit |
| Locust load test (blocking) | `locust-load-test` | Locust — p95 < 500ms, error rate < 1% |
| Lockfile freshness | `lockfile-check` | pip-compile |
| Migration naming | `migration-naming-lint` | custom script |
| Contract tests | `contract-tests` | pytest contract tests (`tests/contract/`) — validates error envelope shape, pagination contracts, and API response schemas |
| Secret scanning | `secret-scanning` | gitleaks |
| API path drift | `api-path-drift` | custom script |
| Config drift guard | `config-drift-guard` | custom script (forbidden string scan) |
| Config failfast proof | `config-failfast-proof` | custom script |
| Quality trend | `quality-trend` | custom script |
| OpenAPI contract check | `openapi-contract-check` | custom script |
| Audit acceptance artifacts | `audit-acceptance-artifacts` | custom script |

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
