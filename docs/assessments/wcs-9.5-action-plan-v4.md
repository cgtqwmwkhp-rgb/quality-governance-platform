# WCS 9.5 Action Plan v4 — Sequenced Execution

**Date**: 2026-04-03
**Strategy**: Fix violations first, then flip gates. Never raise a threshold before adding tests.

---

## Phase 1: Pre-Flight Fixes (must complete before any gate hardening)

### 1A. Fix license compliance allow-list
- Add variant license names: `MIT License`, `BSD License`, `Mozilla Public License 2.0 (MPL 2.0)`, `ISC License (ISCL)`, `Python Software Foundation License`, `The Unlicense (Unlicense)`, `Apache-2.0 OR BSD-3-Clause`
- Then remove `|| echo` fallback

### 1B. Create .markdownlint-cli2.jsonc config file
- Move inline config to file
- Fix CI to reference config file instead of inline JSON
- Run markdownlint and fix any critical issues in docs/

### 1C. Fix compliance freshness check scope
- Ensure `dpia-template.md` and other templates are excluded from freshness check
- Then make freshness check blocking (exit 1)

### 1D. Fix alembic check exit logic
- The current code swallows the exit code; fix to `sys.exit(1)` only on true drift (not on "Target database is not up to date" which is benign)

### 1E. Fix Dockerfile determinism
- Remove `apt-get upgrade -y` from both stages (base image is already digest-pinned)
- Keep `apt-get update` for package index only

## Phase 2: CI Gate Hardening (after Phase 1 fixes)

### 2A. Flip license compliance to blocking (after 1A)
### 2B. Flip docs-lint to blocking (after 1B — markdownlint only, keep link-check advisory)
### 2C. Flip compliance freshness to blocking (after 1C)
### 2D. Flip alembic check to blocking (after 1D)
### 2E. Fix mutation testing error handling
- Do NOT remove `|| true` from `mutmut run` (it exits 2 on survived mutations, which is normal)
- Instead: tighten survived threshold from 50 to 40
### 2F. Keep ZAP at `warn` for now — baseline scan finds informational issues that would break CI
### 2G. Keep radon as advisory — 25+ grade D/F functions exist; can't block without massive refactor
### 2H. Keep SLSA continue-on-error — signing infra may not be fully configured
### 2I. Config-drift env parity — add exit 1 on drift detection

## Phase 3: Data Model & Error Migration (no CI dependencies)

### 3A. Add CheckConstraints to 5 critical models
- `incident.py`: severity BETWEEN 1 AND 5, priority BETWEEN 1 AND 5
- `complaint.py`: severity BETWEEN 1 AND 5
- `rta.py`: severity BETWEEN 1 AND 5
- `near_miss.py`: severity BETWEEN 1 AND 5
- `audit.py`: overall_score >= 0

### 3B. Complete error migration
- Re-audit ALL route files for plain-string HTTPException
- Migrate remaining to api_error() envelope
- Update error-migration-tracker.md with accurate percentages

### 3C. Add optimistic locking version column
- Add `version` column to AuditRun model for OCC
- Add CheckConstraint for version >= 1

## Phase 4: Test Hardening & Coverage

### 4A. Tighten CUJ E2E test assertions
- CUJ-02: Assert 201 only on create endpoints
- CUJ-03: Assert 200/201, add checklist completion test
- CUJ-05: Assert 201, verify witness record
- CUJ-06: Assert 201, verify upload
- CUJ-07: Assert 201, verify ordering

### 4B. Add axe a11y tests for 10 more components
- DataTable, Input, Select, Tabs, Switch, DropdownMenu, RadioGroup, Checkbox, Avatar, Tooltip

### 4C. Add 3 golden fixture files
- `action.json`, `vehicle_check.json`, `workflow.json`

### 4D. Add contract tests for 3 more endpoints
- `/api/v1/near-misses`, `/api/v1/incidents`, `/api/v1/actions`

### 4E. Add trace-propagation test
- Verify W3C traceparent header propagation through middleware

### 4F. THEN raise coverage threshold from 48% to 52% (only after 4A-4E)

## Phase 5: Observability & Telemetry Wiring

### 5A. Wire 5 metric instruments
- `risks.created` in risks route
- `auth.login` / `auth.failures` in auth route
- `documents.uploaded` in documents route
- `api.error_rate_5xx` in error handler middleware

### 5B. Add page_view telemetry in frontend
- Create router listener that fires page_view on route change

### 5C. Add OTel package presence check in CI
- Verify opentelemetry-* packages in requirements.txt

### 5D. Update alerting-rules.md
- Move wired instruments from Ready-to-Activate to Active

## Phase 6: Frontend & UX

### 6A. Install Storybook
- `npx storybook@latest init` in frontend/
- Configure for Vite + React + TypeScript
- Create stories for 8 core components: Button, Card, DataTable, Dialog, Input, Select, Badge, Toast

### 6B. Welsh i18n expansion
- Add 100+ Welsh translation keys
- Raise i18n-check.mjs threshold from 65% to 70%
- Add centralized date formatting utility

### 6C. Promote Lighthouse FCP/TBT from warn to error

## Phase 7: Documentation & Governance

### 7A. Update stale docs
- DPIA: Mark Art. 20 as Implemented (code exists)
- locale-coverage.md: Update to 69.9% + new count
- error-migration-tracker.md: Re-audit with accurate percentages

### 7B. Add GDPR Art. 18 restriction flag docs
- Document the gap and planned implementation path

### 7C. Create ADR-0013 for IaC adoption
- Document the decision to adopt Bicep
- Include alternatives considered

### 7D. Create L1/L2 support escalation runbook

### 7E. Add ADR review cadence
- Annual review schedule in governance docs

## Phase 8: Supportability & Config

### 8A. Expand admin_cli.py
- Add `tenant-info` command
- Add `user-lookup` command

### 8B. Add .env.example completeness check in CI
- Script to compare .env.example keys with Settings class fields

### 8C. Create basic Bicep template
- Azure App Service + PostgreSQL + Storage Account
- NOT deployed — just codified for D31

## Dimensions Coverage Matrix

| Dim | Phase(s) | Actions |
|-----|----------|---------|
| D01 | 4A | Tighten CUJ tests |
| D02 | 6A | Storybook |
| D03 | 4B, 6C | Axe tests, Lighthouse |
| D04 | 6C | Lighthouse thresholds |
| D05 | 7D | Support escalation runbook (partial) |
| D06 | 2F noted | ZAP stays warn (documented rationale) |
| D07 | 7A, 7B | DPIA update, Art. 18 docs |
| D08 | 1C, 2C | Compliance freshness blocking |
| D09 | 1D, 2D | Alembic check blocking |
| D10 | 3B | Error migration completion |
| D11 | 3A | CheckConstraints |
| D12 | 1D, 2D | Alembic check blocking |
| D13 | 4E, 5A-D | Trace test, instruments, OTel check |
| D14 | 3B | Error migration completion |
| D15 | 4A-E, 4F | Tests first, then threshold |
| D16 | 4C | Golden fixtures |
| D17 | 1A-E, 2A-I | Gate hardening |
| D18 | — | No safe code-only change (needs infra) |
| D19 | 8B | .env.example check |
| D20 | 1A, 2A | License blocking |
| D21 | 2G noted | Radon stays advisory (too many violations) |
| D22 | 1B, 2B | Markdownlint blocking |
| D23 | 7D | Support escalation runbook |
| D24 | 3C | Optimistic locking expansion |
| D25 | — | Locust threshold change risky (may fail CI) |
| D26 | — | Per-tenant attribution needs Azure infra |
| D27 | 6B | Welsh expansion, date formatter |
| D28 | 5A-D | Telemetry wiring |
| D29 | 7C, 7E | ADR-0013, review cadence |
| D30 | 1E | Remove apt-get upgrade |
| D31 | 8C | Bicep template |
| D32 | 8A | Admin CLI expansion |
