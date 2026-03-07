# World-Class Assessment - Uplift Plan (Round 2, Refreshed)

Date: 2026-03-07
Target: World-Class threshold WCS >= 9.5 for every in-scope dimension

## 6) Quick Wins Engine (Small Effort / High Value, Top 12)

Top candidates are Effort S/M, Value High, linked to critical functions.

1. Promote local hardening tranche to `main` + prod with proof  
   - CF/Dimensions: CF5, D17 D18 D30  
   - Locations: local modified files already identified in `git status`  
   - DoD: merged commit deployed; prod `/api/v1/meta/version` build SHA equals merged SHA  
   - Validation: GH deploy run success + runtime SHA check  
   - Rollback: revert merge commit  
   - Expected WCS lift: +0.4 to +0.9

2. Canonical endpoint parity gate (API + frontend)  
   - CF/Dimensions: CF5, D31 D19  
   - Locations: `docs/evidence/environment_endpoints.json`, deploy workflows  
   - DoD: DNS/TLS/HTTP parity check blocks mismatches  
   - Validation: probe job in CI/deploy proof  
   - Rollback: advisory mode with expiry waiver  
   - Expected WCS lift: +0.5 to +1.0

3. Hard-block integration and contract CI gates  
   - CF/Dimensions: CF5, D17 D30  
   - Locations: `.github/workflows/ci.yml`, `tests/contract/test_api_contracts.py`  
   - DoD: no soft-pass behavior for critical jobs; failures block merge  
   - Validation: intentional failing contract test causes all-checks failure  
   - Rollback: workflow commit revert  
   - Expected WCS lift: +0.8 to +1.3

4. Enforce release signoff separation-of-duties  
   - CF/Dimensions: CF5, D18 D29 D06  
   - Locations: `.github/workflows/deploy-production.yml`, `scripts/governance/validate_release_signoff.py`  
   - DoD: missing signoff fails; governance and CAB approvers must differ  
   - Validation: workflow simulation with invalid signoff  
   - Rollback: controlled emergency override with expiry  
   - Expected WCS lift: +0.6 to +1.1

5. Resolve staging parity contradiction  
   - CF/Dimensions: CF5, D31 D19  
   - Locations: `docs/evidence/environment_endpoints.json`, deploy workflows, drift checks  
   - DoD: source-of-truth parity check passes in CI  
   - Validation: parity script run in PR and main  
   - Rollback: artifact restore + temporary parity gate disable  
   - Expected WCS lift: +0.5 to +1.0

6. Make Python lockfile mandatory and hash-verified  
   - CF/Dimensions: CF5, D20 D30  
   - Locations: `.github/workflows/ci.yml`, lockfile update workflow, `requirements.lock`  
   - DoD: missing/stale lockfile fails build  
   - Validation: dependency-change PR without lockfile update fails  
   - Rollback: temporary exception allowlist with expiry  
   - Expected WCS lift: +0.5 to +0.9

7. Unify pytest async loop scope  
   - CF/Dimensions: CF5, D16 D30  
   - Locations: `pyproject.toml`, `pytest.ini`  
   - DoD: single scope value, documented rationale, no contradictions  
   - Validation: repeat-run stability tests on flaky subset  
   - Rollback: revert config change  
   - Expected WCS lift: +0.4 to +0.8

8. Standardize API error envelope contract  
   - CF/Dimensions: CF1 CF2, D10 D14  
   - Locations: `src/api/routes/users.py`, `src/api/routes/risks.py`, `src/api/routes/audits.py`, tests  
   - DoD: all core 4xx/5xx responses match canonical envelope schema  
   - Validation: integration contract tests for error shape  
   - Rollback: middleware adapter fallback  
   - Expected WCS lift: +0.5 to +0.9

9. Privacy baseline + retention controls  
   - CF/Dimensions: CF3, D07 D24  
   - Locations: `docs/privacy/*`, portal-related write paths, scheduler job  
   - DoD: retention policy documented and technically enforced with evidence  
   - Validation: purge integration tests + PII leakage checks  
   - Rollback: disable purge scheduler while retaining audit evidence  
   - Expected WCS lift: +0.8 to +1.4

10. Promote critical accessibility checks to blocking  
   - CF/Dimensions: CF2, D03  
   - Locations: `frontend/eslint.config.cjs`, frontend CI job  
   - DoD: selected critical a11y rules fail CI on violation  
   - Validation: intentionally failing a11y fixture  
   - Rollback: severity downgrade with expiry waiver  
   - Expected WCS lift: +0.4 to +0.8

11. Promote i18n key check to blocking for FE changes  
   - CF/Dimensions: CF2, D27 D17  
   - Locations: `.github/workflows/ci.yml`, `scripts/i18n-check.mjs`  
   - DoD: missing i18n key blocks FE-related PRs  
   - Validation: remove key in test branch, expect CI failure  
   - Rollback: advisory mode with waiver expiration  
   - Expected WCS lift: +0.3 to +0.7

12. Add migration safety suite  
   - CF/Dimensions: CF3 CF5, D12 D24  
   - Locations: `tests/migrations/*`, migration workflow stages  
   - DoD: upgrade+downgrade+data-preservation checks block release  
   - Validation: migration fixture with reversible and non-reversible cases  
   - Rollback: temporary downgrade-check waiver only  
   - Expected WCS lift: +0.7 to +1.2


## 7) Critical Bars Hardening Plan (P0 first)

### Security Hardening Gates
- Current evidence:
  - Auth dependencies and role checks exist
  - Security scans and post-deploy auth checks exist in production workflow
- Gap:
  - Endpoint parity confidence is still weakened by unresolved staging/frontend canonical host evidence
- Implementation:
  1. Keep hard-fail CI and SoD signoff enforcement as non-negotiable
  2. Add canonical endpoint parity gate for API + frontend
  3. Add release control-board artifact proving signoff+parity+sha
- Done criteria:
  - No production deployment can run without validated signoff
  - CI critical checks cannot pass on failing tests

### Data Integrity Gates
- Current evidence:
  - Idempotency middleware present
  - Optimistic conflict pattern in investigations
  - Alembic migration execution in CI/deploy
- Gap:
  - Integrity controls not uniformly implemented across all critical write paths
  - Migration safety is not yet comprehensively tested
- Implementation:
  1. Add migration safety test suite
  2. Extend optimistic concurrency patterns to high-contention entities
  3. Add deterministic contract checks for pagination/error envelopes
- Done criteria:
  - Critical writes protected by explicit concurrency controls
  - Migration safety tests are blocking

### Release Safety Gates
- Current evidence:
  - Deterministic SHA verification in deploy workflows
  - Rollback runbooks and strict release gate docs present
- Gap:
  - Environment parity endpoint contradiction (especially frontend canonical host)
  - Local hardening tranche not yet promoted
- Implementation:
  1. Resolve parity mismatch and enforce parity checker
  2. Make lockfile mandatory
  3. Add release summary gate for parity + signoff + lockfile compliance
- Done criteria:
  - Release summary is fully green on parity, signoff, reproducibility

## 8) World-Class Roadmap (3 Horizons)

### Horizon A (0-2 weeks): Safety, determinism, testability
- Epics:
  - Promote pending local hardening tranche
  - Canonical endpoint parity gate
  - Migration safety suite bootstrap
  - Release control-board artifact
- Entry criteria:
  - Current mainline pipeline green
  - Named owners assigned
- Exit criteria:
  - Critical bars blocking and auditable
  - Parity contradictions (API + frontend canonical hosts) resolved or waived with expiry

### Horizon B (2-6 weeks): Core quality uplift on critical path
- Epics:
  - Complete API error contract coverage + lint policy
  - Privacy baseline + retention controls
  - Journey-level SLI dashboard and alerting
  - Concurrency/write-integrity standardization
- Entry criteria:
  - Horizon A controls stable for one week
- Exit criteria:
  - Core flows have deterministic contracts and measurable reliability/security telemetry

### Horizon C (6-12 weeks): Resilience automation and 5/5 completion
- Epics:
  - Capacity and cost governance
  - Accessibility/i18n hard-gate maturity
  - Governance/doc freshness automation
- Entry criteria:
  - Horizon B controls operating in production with no severe regressions
- Exit criteria:
  - Repeatable evidence of D01-D32 controls at 9.5+ quality bar

## 9) PR-Ready Backlog

Detailed copy/paste backlog (25 items, sorted by PS then effort) is in:
- `docs/assessments/backlog_pr_ready.yaml`

## 10) Acceptance-Test Matrix (World-Class proof)

Detailed matrix is in:
- `docs/assessments/acceptance_test_matrix.csv`

## 11) World-Class Checklist (D01-D32 observable criteria)

- D01: Top 3 journeys have deterministic E2E tests and measurable success SLAs.
- D02: UX acceptance checks are automated for core navigation and workflow completion.
- D03: Critical accessibility violations block CI for changed code.
- D04: FE bundle and API latency budgets block regressions.
- D05: Reliability SLOs and rollback drill cadence are documented and evidenced.
- D06: Security controls are blocking and auditable in CI/CD and runtime checks.
- D07: Privacy lifecycle controls are documented and technically enforced.
- D08: Compliance controls are mapped to evidence artifacts with ownership.
- D09: Layering boundaries are explicit and protected from architectural erosion.
- D10: API contracts are deterministic and fully regression-tested.
- D11: Canonical data model enforced; legacy writes sunsetted.
- D12: Migration safety tests cover upgrade, downgrade, and integrity.
- D13: Observability captures all critical flow metrics with actionable alerts.
- D14: Unified error envelopes with stable codes and request correlation IDs.
- D15: Testing pyramid balanced and risk-weighted toward critical bars.
- D16: Fixture strategy deterministic, maintainable, and fail-fast.
- D17: CI gate integrity has no critical soft-pass paths.
- D18: Release pipeline enforces immutable promotion and independent approvals.
- D19: Configuration validation is fail-fast and drift-guarded.
- D20: Dependencies are pinned, scanned, and reproducible.
- D21: Static quality gates prevent maintainability decay.
- D22: Docs are current, owned, and validated by policy checks.
- D23: Incident and rollback runbooks are regularly exercised and evidenced.
- D24: Data consistency controls cover idempotency, concurrency, and state transitions.
- D25: Capacity and saturation thresholds are measured and governed.
- D26: Cost controls are monitored against explicit budgets.
- D27: i18n readiness and key completeness are enforced in CI.
- D28: Product and operational telemetry are tied to decision-making.
- D29: ADR and governance evidence is mandatory for major architectural change.
- D30: Build/release determinism is fully auditable from source to runtime.
- D31: Environment parity is continuously validated and contradiction-free.
- D32: Supportability and operability evidence supports rapid incident recovery.

## B) Risk and ROI tags

Applied per backlog item in:
- `docs/assessments/backlog_pr_ready.yaml`

## C) No-scope-creep guardrail

Applied per backlog item in:
- `docs/assessments/backlog_pr_ready.yaml`

## D) Evidence index

Detailed evidence index is in:
- `docs/assessments/evidence_index.md`

## Validation Checklist (Round 2)

- Quick wins all Effort S/M + Value High + CF-linked: Yes
- Critical bars include security, data integrity, release safety with done criteria: Yes
- Roadmap has three horizons with entry/exit/dependencies/risks: Yes
- Backlog items include bounded change, DoD, tests, observability, rollback, tags, out-of-scope: Yes

