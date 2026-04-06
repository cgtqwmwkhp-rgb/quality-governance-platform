# Test Coverage Baseline (D15)

Current coverage targets and enforcement points across the CI pipeline.

## Coverage Gate Configuration

**Authoritative enforcement (verify on each release):** read the cited lines in-repo; this table was reconciled to match them at commit time.

| Gate | Location | Enforced threshold | Evidence (line) |
|------|----------|-------------------|-----------------|
| Unit tests `--cov-fail-under` | `.github/workflows/ci.yml` → job `unit-tests` | **44%** | `pytest` step line **322** |
| Integration tests `--cov-fail-under` | `.github/workflows/ci.yml` → job `integration-tests` | **42%** | `pytest` step in `integration-tests` job |
| Combined report `fail_under` | `pyproject.toml` `[tool.coverage.report]` | **70%** | `fail_under = 70` line **133** |

**Note:** Unit and integration jobs enforce **per-job** coverage of `src` during that job’s pytest run; `pyproject.toml` `fail_under` applies to **combined** coverage reports (e.g. local/aggregate tooling), not necessarily the same numerator as either job alone.

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
