# WCS 9.5 Gap Closure Blueprint — v4

**Date**: 2026-04-03
**Baseline**: Assessment post-v3 (avg WCS 6.6, commit `6f0d4baf`)
**Target**: ≥ 9.5 WCS across all 32 dimensions

---

## Workstream 1: CI Gate Hardening (Dims: D06, D08, D12, D15, D17, D20, D21, D22, D30)

Convert 12 advisory CI gates to blocking. This is the single highest-ROI change.

| # | Gate | File | Current | Action |
|---|------|------|---------|--------|
| 1 | ZAP `fail_action` | `ci.yml` | `warn` | Change to `fail` |
| 2 | Radon complexity | `ci.yml` | `::warning::` only | `exit 1` on grade D+ |
| 3 | License compliance | `ci.yml` | `\|\| echo` fallback | Remove fallback |
| 4 | Docs-lint markdownlint | `ci.yml` | `\|\| echo` fallback | Remove fallback |
| 5 | Docs-lint link-check | `ci.yml` | `\|\| echo` fallback | Remove fallback |
| 6 | SLSA attestation | `deploy-staging.yml` | `continue-on-error: true` | Remove |
| 7 | `alembic check` | `ci.yml` | Never exits non-zero | Add `sys.exit(result.returncode)` |
| 8 | Compliance freshness | `ci.yml` | `::warning::` only | `exit 1` on stale |
| 9 | Mutation `mutmut run` | `ci.yml` | `\|\| true` | Remove (keep threshold check) |
| 10 | SBOM cyclonedx fallback | `ci.yml` | Triple `\|\|` chain | Fail on error |
| 11 | `apt-get upgrade` | `Dockerfile` | Non-deterministic | Remove from both stages |
| 12 | Config-drift env parity | `ci.yml` | Warning only | Exit 1 on drift |

## Workstream 2: CUJ Test Hardening (Dim: D01)

Tighten 5 CUJ E2E test assertions to reject 4xx/5xx on happy paths:
- `test_cuj02_capa_from_incident.py`: Assert 201 on create, verify CAPA linkage
- `test_cuj03_daily_vehicle_checklist.py`: Assert 200/201, add checklist completion flow
- `test_cuj05_witness_details.py`: Assert 201, verify witness record
- `test_cuj06_evidence_upload.py`: Assert 201, verify upload linkage
- `test_cuj07_running_sheet.py`: Assert 201, verify ordering

## Workstream 3: Storybook Foundation (Dim: D02)

- Install Storybook for React/Vite/TS
- Create `.storybook/main.ts` + `preview.ts`
- Write stories for 8 core components: Button, Card, DataTable, Dialog, Input, Select, Badge, Toast
- Add `storybook-build` CI job (advisory initially)

## Workstream 4: Accessibility Expansion (Dim: D03)

- Add axe tests for 10 more components (DataTable, Input, Select, Tabs, Switch, DropdownMenu, RadioGroup, Checkbox, Avatar, Tooltip)
- Promote FCP/TBT Lighthouse thresholds from `warn` to `error`
- Add `aria-describedby` audit for form components

## Workstream 5: Data Model Constraints (Dim: D11)

Add `CheckConstraint` to 5 critical models:
- `incident.py`: severity BETWEEN 1 AND 5
- `complaint.py`: severity BETWEEN 1 AND 5
- `rta.py`: severity BETWEEN 1 AND 5
- `near_miss.py`: severity BETWEEN 1 AND 5
- `audit.py`: score >= 0

## Workstream 6: Error Migration Completion (Dims: D10, D14)

- Re-audit ALL route files for plain-string HTTPException
- Migrate any remaining plain-string errors to `api_error()` envelope
- Update `docs/api/error-migration-tracker.md` with accurate per-module percentages
- Target: 100% structured errors across all modules

## Workstream 7: Observability Wiring (Dims: D13, D28)

- Add trace-propagation test (W3C traceparent header validation)
- Wire 5 priority metric instruments: `risks.created`, `auth.login`, `auth.failures`, `documents.uploaded`, `api.error_rate_5xx`
- Add `page_view` telemetry in frontend router
- Add OTel package presence check in CI
- Update alerting-rules.md status for wired alerts

## Workstream 8: Documentation Freshness (Dims: D07, D10, D22, D27)

- Update DPIA to reflect existing Art. 20 portability code
- Re-audit and correct error-migration-tracker percentages
- Update locale-coverage.md with actual 69.9% figure
- Create `.markdownlint.json` config file
- Add ADR review cadence to governance docs

## Workstream 9: Type Safety Reduction (Dim: D21)

- Reduce MAX_TYPE_IGNORES from 188 toward 170
- Remove 5 modules from mypy `ignore_errors` block
- Make radon complexity blocking (covered in WS1)

## Workstream 10: Welsh i18n Expansion (Dim: D27)

- Add 100+ Welsh translations to reach ~75% coverage
- Raise i18n-check.mjs threshold from 65% to 72%
- Add centralized date formatting utility using `Intl.DateTimeFormat` with locale
- Update locale-coverage.md

## Workstream 11: Admin CLI + Supportability (Dim: D32)

- Add `tenant-info` command to admin_cli.py
- Add `user-lookup` command
- Add `circuit-breaker-status` command
- Create L1/L2 support escalation runbook

## Workstream 12: Config Validation (Dim: D19)

- Add CI check: `.env.example` completeness vs Settings class
- Strengthen config-drift-guard with schema validation

## Workstream 13: Environment Parity Foundation (Dim: D31)

- Create basic Bicep template for core Azure resources
- Add environment promotion SHA validation in CI
- Document IaC adoption decision in ADR-0013

## Workstream 14: Test Coverage + Data (Dims: D15, D16)

- Raise coverage threshold from 48% toward 55%
- Add 3 more golden fixture files
- Tighten mutation testing threshold from 50 to 35
- Add contract tests for 3 more endpoints
