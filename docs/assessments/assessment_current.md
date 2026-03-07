# World-Class Assessment - Current State (Round 1, Refreshed)

Date: 2026-03-07  
Scope: `quality-governance-platform`  
Method: Evidence-led repository + runtime parity evidence review, deterministic D01->D32.

## 1) Executive Summary

- Average maturity: **3.61 / 5.00**
- Average WCS: **6.4 / 10.0**
- Confidence: **Medium** (strong direct evidence for CI/CD, release, auth; weak/missing privacy-capacity-cost artifacts)
- Previous baseline used: prior scorecard in `docs/assessments/scorecard.csv` (same D01-D32 framework)
- Biggest improvements: D17 (+0.6), D30 (+0.6), D20 (+0.5), D31 (+0.5), D14 (+0.4)
- Biggest regressions: none observed
- Top strengths:
  - D17 CI gates hardened in critical jobs (`.github/workflows/ci.yml`)
  - D18 release governance hardening (`.github/workflows/deploy-production.yml`)
  - D29 governance controls with SoD validation (`scripts/governance/validate_release_signoff.py`)
  - D14 route+middleware error normalization (`src/api/middleware/error_handler.py`, `src/api/utils/errors.py`)
  - D06 strong authz boundaries and runtime security checks (`src/api/dependencies/__init__.py`, deploy security checks)
- Top deficits:
  - D07 privacy evidence/controls incomplete (`docs/privacy/*` missing)
  - D25 scalability/capacity evidence incomplete (no SLO/load pack)
  - D26 cost governance evidence incomplete
  - D12 migration safety not yet proven by dedicated blocking suite
  - D31 parity still partly contradictory for staging/frontend canonical runtime hosts
- World-Class Breach List (WCS < 9.5): **D01-D32 (all dimensions)**

## 2) Critical Function Map (CF1..CF5)

### CF1 - Auth/session + authorization boundaries
- Blast radius: High
- Evidence:
  - `src/api/dependencies/__init__.py`
  - `src/core/security.py`
  - `src/api/routes/users.py`
- Current risks:
  - Contract consistency across route families remains uneven

### CF2 - Primary business workflows (top 3 journeys)
- Blast radius: High
- Journeys:
  1. Portal intake/tracking (`src/api/routes/employee_portal.py`)
  2. Audit template -> run -> responses -> findings (`src/api/routes/audits.py`)
  3. Risk lifecycle (`src/api/routes/risks.py`)
- Current risks:
  - Journey-level telemetry/SLO coverage still partial

### CF3 - Data writes + transitions + side effects
- Blast radius: High
- Evidence:
  - `src/main.py` (idempotency middleware)
  - `src/api/routes/investigations.py` (conflict logic)
  - `alembic/env.py` + deploy migration steps
- Current risks:
  - Concurrency and migration-integrity controls are not uniformly proven

### CF4 - External integrations
- Blast radius: Medium-High
- Evidence:
  - `.github/workflows/deploy-staging.yml`
  - `.github/workflows/deploy-production.yml`
  - `scripts/governance/prod-dependencies-gate.sh`
- Current risks:
  - Staging/runtime endpoint evidence mismatch lowers confidence

### CF5 - Release/deploy + rollback + config changes
- Blast radius: High
- Evidence:
  - `.github/workflows/ci.yml`
  - `.github/workflows/deploy-staging.yml`
  - `.github/workflows/deploy-production.yml`
  - `docs/runbooks/AUDIT_ROLLBACK_DRILL.md`
- Current risks:
  - Local hardening tranche pending promotion
  - Canonical frontend/staging parity evidence inconsistent

### Mandatory Safety Gates (pre-broad changes)
1. Critical CI jobs must remain hard-fail.
2. Release signoff must be pre-provided and SoD-valid.
3. Lockfile must exist and pass hash-freshness checks.
4. Migration safety suite must be blocking.
5. Endpoint parity (API+frontend) must pass runtime resolvability checks.

## 3) Scorecard Table

Full deterministic 32-row scorecard:
- `docs/assessments/scorecard.csv`

Scoring model:
- Base WCS = `(maturity / 5) * 10`
- Final WCS = `round(base_wcs * CM, 1)`
- WCS gap = `max(0, 9.5 - Final WCS)`
- Priority Score = `round(WCS gap * CW, 1)`

## 4) Findings Register (P0/P1 only)

Detailed register:
- `docs/assessments/findings_register.csv`

Highest priority focus:
- F-001 parity endpoint contradiction and runtime confidence gap
- F-002 missing blocking migration safety suite
- F-003 non-uniform write-concurrency guards
- F-004 partial route-level error contract coverage
- F-005 accessibility hard-gating incomplete

## 5) Evidence Gaps

### GAP-001 - Privacy baseline pack
- Missing: DPIA/retention/DSR control artifacts
- Why it blocks confidence: prevents high-confidence D07 scoring
- Expected location: `docs/privacy/*`
- Minimal content: data inventory, lawful basis, retention matrix, DSR workflow

### GAP-002 - Capacity/SLO evidence
- Missing: journey SLO definitions + load evidence
- Why it blocks confidence: weak D25 confidence
- Expected location: `docs/ops/slo.md`, `docs/evidence/perf/*`
- Minimal content: targets, test profile, pass/fail thresholds, mitigation playbooks

### GAP-003 - FinOps baseline
- Missing: cost budgets and response runbook
- Why it blocks confidence: weak D26 confidence
- Expected location: `docs/ops/cost-governance.md`
- Minimal content: budget thresholds, alert routing, owner response actions

### GAP-004 - Canonical endpoint parity contract
- Missing: authoritative staging/frontend host contract with runtime verification artifacts
- Why it blocks confidence: weak D31 parity confidence
- Expected location: `docs/evidence/environment_endpoints.json` + deploy proof artifacts
- Minimal content: canonical hosts, DNS/TLS expectation, probe results per deployment

### GAP-005 - Migration safety suite artifacts
- Missing: dedicated upgrade/downgrade/data-preservation tests
- Why it blocks confidence: weak D12/D24 confidence
- Expected location: `tests/migrations/*`
- Minimal content: reversible/unreversible cases, idempotency checks, data-preservation assertions

## A) Contradictions Resolver

### C-001
- Issue: Staging/frontend endpoint evidence does not cleanly align with runtime-resolvable hosts.
- Evidence:
  - `docs/evidence/environment_endpoints.json`
  - runtime probes during assessment (staging host unresolved; listed SWA hosts TLS/404 mismatch)
- Severity: P1+

### C-002
- Issue: API parity is strong for production (`build_sha`/health/readiness), but frontend parity evidence is weaker.
- Evidence:
  - `https://app-qgp-prod.azurewebsites.net/api/v1/meta/version`
  - `https://app-qgp-prod.azurewebsites.net/readyz`
  - listed SWA host probe outcomes
- Severity: P1+

### C-003
- Issue: Local hardening tranche exists but is not yet promoted, creating temporary local-vs-production drift.
- Evidence:
  - `git status` modified/untracked assessment state
  - production `build_sha` matches `origin/main` merge SHA, not local working tree
- Severity: P1+

## Validation Checklist (Round 1)

- Every dimension has evidence pointers or an explicit evidence gap: Yes
- WCS/CM/PS math is deterministic and reproducible: Yes
- Ordering is fixed D01->D32: Yes
- Critical-path anchoring performed before scoring: Yes

