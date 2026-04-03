# Test Coverage Baseline (D15)

Current coverage targets and enforcement points across the CI pipeline.

## Coverage Gate Configuration

| Gate | Location | Previous Threshold | Current Threshold |
|------|----------|--------------------|-------------------|
| Unit tests `--cov-fail-under` | `.github/workflows/ci.yml` (unit-tests job) | 38% | 43% |
| Integration tests `--cov-fail-under` | `.github/workflows/ci.yml` (integration-tests job) | 40% | 43% |
| Combined report `fail_under` | `pyproject.toml` `[tool.coverage.report]` | 45% | 48% |

## Coverage Tracking Strategy

- **CI enforcement**: Every PR must pass `--cov-fail-under` thresholds in both unit and integration test jobs.
- **Combined report**: `pyproject.toml` `fail_under` enforces total project coverage across both suites.
- **Trend monitoring**: The `quality-trend` CI job tracks historical coverage metrics. Coverage XML is uploaded as a CI artifact for longitudinal analysis.
- **Module-level tracking**: Coverage reports include per-module breakdowns in `term` output; teams should review modules below 50% for targeted improvement.

## Mutation Testing

Mutation testing (via `mutmut`) runs as a weekly advisory CI job (`mutation-testing` in `ci.yml`). It is configured as advisory (not blocking) to avoid false-positive gate failures on mutants in generated code or infrastructure modules.

**Rationale for advisory status**: Mutation testing produces variable results depending on test isolation and fixture availability. Promoting to a blocking gate requires:
1. A stable mutant kill rate baseline >= 70%
2. Explicit suppression rules for known false-positive modules
3. A documented review process for surviving mutants

These prerequisites are tracked for future implementation.

## Related Documents

- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — performance SLOs
- [`docs/testing/test-data-strategy.md`](../testing/test-data-strategy.md) — test data strategy
- [`pyproject.toml`](../../pyproject.toml) — coverage configuration
