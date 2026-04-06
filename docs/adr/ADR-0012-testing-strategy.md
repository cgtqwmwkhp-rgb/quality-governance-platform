# ADR-0012: Testing Strategy

## Status
Accepted

## Date
2026-04-03

## Context
The platform requires comprehensive quality assurance across unit, integration, e2e, contract, and performance testing layers.

## Decision
We adopt a test pyramid strategy:
- **Unit tests** (pytest): minimum 52% line coverage, enforced in CI
- **Integration tests** (pytest): database and service integration, same coverage floor
- **E2E tests** (pytest): critical user journeys (CUJ-01 through CUJ-10) with strict assertions
- **Contract tests**: OpenAPI schema validation, error envelope format, pagination contracts
- **Performance tests** (Locust): p95 < 500ms, error rate < 1%, run as blocking CI gate
- **Mutation testing** (mutmut): scheduled weekly, results tracked for trend analysis
- **Accessibility tests** (axe-core): component-level and route-level coverage
- **Security tests**: Bandit, pip-audit, gitleaks, secret scanning as blocking gates

## Consequences
- Coverage thresholds are enforced in CI and can only ratchet upward
- All CUJ tests must have strict assertions (no tolerating 401/404 on happy paths)
- Performance regressions detected by Locust block merges
- Mutation testing trends inform test quality improvements
