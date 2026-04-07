# Test Coverage Baseline (D15)

Current coverage targets and enforcement points across the CI pipeline.

## Coverage Gate Configuration

**Authoritative enforcement (verify on each release):** read the cited lines in-repo; this table was reconciled to match them at commit time.

| Gate | Location | Enforced threshold | Evidence (line) | Last Updated |
|------|----------|-------------------|-----------------|--------------|
| Unit tests `--cov-fail-under` | `.github/workflows/ci.yml` → job `unit-tests` | **52%** | `pytest` step line 322 | 2026-04-07 (EG-05: raised 44→48→52) |
| Integration tests `--cov-fail-under` | `.github/workflows/ci.yml` → job `integration-tests` | **47%** | `pytest` step in `integration-tests` job | 2026-04-07 (EG-05: raised 42→43→47) |
| Combined report `fail_under` | `pyproject.toml` `[tool.coverage.report]` | **70%** | `fail_under = 70` | Stable |
| Mutation survival rate | `.github/workflows/ci.yml` → job `mutation-testing` | **advisory (weekly)** | `mutation-testing` schedule job | 2026-04-07 (runs weekly; mutmut v3 CLI change prevents per-PR blocking gate) |

**Note:** Unit and integration jobs enforce **per-job** coverage of `src` during that job’s pytest run; `pyproject.toml` `fail_under` applies to **combined** coverage reports (e.g. local/aggregate tooling), not necessarily the same numerator as either job alone.

## Coverage Tracking Strategy

- **CI enforcement**: Every PR must pass `--cov-fail-under` thresholds in both unit and integration test jobs.
- **Combined report**: `pyproject.toml` `fail_under` enforces total project coverage across both suites.
- **Trend monitoring**: The `quality-trend` CI job tracks historical coverage metrics. Coverage XML is uploaded as a CI artifact for longitudinal analysis.
- **Module-level tracking**: Coverage reports include per-module breakdowns in `term` output; teams should review modules below 50% for targeted improvement.

## Mutation Testing

Mutation testing (via `mutmut`) runs as a blocking CI gate on **push to main** and **PRs targeting main**, plus a weekly scheduled run (`mutation-testing` in `ci.yml`).

**Status (2026-04-07):** Weekly advisory schedule. mutmut v3.x CLI changes prevent per-PR blocking gate — using `mutmut<3` pin for stable CLI. Target: promote to blocking gate once CI runner stability is proven over 4 weekly runs with ≤30% survival.

| Configuration | Value |
|--------------|-------|
| Tool | `mutmut<3` (v2.x pinned for stable CLI compatibility) |
| Scope | `src/domain/services/` |
| Trigger | Weekly schedule (Sundays) |
| Survival threshold | Advisory; target ≤30% (not yet enforced as blocking) |
| Report | Uploaded as `mutation-testing-report` artifact (30 days retention) |

## Related Documents

- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — performance SLOs
- [`docs/testing/test-data-strategy.md`](../testing/test-data-strategy.md) — test data strategy
- [`pyproject.toml`](../../pyproject.toml) — coverage configuration
