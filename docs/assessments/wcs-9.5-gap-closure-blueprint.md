# WCS 9.5 Gap Closure Blueprint

**Target**: Every dimension at WCS >= 9.5 (non-negotiable)
**Formula**: WCS = (Maturity/5) × 10 × CM — requires Mat 5.0 + CM >= 0.95
**Date**: 2026-04-03
**Prior Avg WCS (verified)**: 6.3 / 10

---

## Workstream A: Fix Wrong File/Endpoint References (15 fixes across 10 docs)

### A1. build-reproducibility-proof.md
- Replace `/api/v1/health/build` → `/api/v1/meta/version` (3 occurrences: table row, curl command, verification step)
- Replace `python:3.11-slim` → `python:3.11-slim-bookworm` (with digest reference to Dockerfile)
- Fix response field names: `build_sha`, `build_time`, `app_name`, `environment`
- **Impacts**: D30

### A2. diagnostics-endpoint-guide.md
- Replace `/api/v1/health/build` → `/api/v1/meta/version` (table + troubleshooting curl)
- Fix `/api/v1/health/metrics/resources` auth: "Yes (admin)" → "No"
- Fix `/api/v1/feature-flags` auth: "Yes (admin)" → "Yes (any authenticated user)"
- Fix troubleshooting workflow curl commands to use correct endpoint
- **Impacts**: D32

### A3. idempotency-and-locking.md
- Replace `src/infrastructure/middleware/rate_limiter.py` → `src/api/middleware/idempotency.py` (table + Related Docs)
- Fix log behavior: "warning" → "debug"; fix message text to match actual code
- Update Related Documents section to reference idempotency.py for idempotency, rate_limiter.py for rate limiting only
- **Impacts**: D24

### A4. error-migration-tracker.md
- Replace target JSON format with actual error_handler.py envelope: `{"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}`
- Recompute endpoint counts per module from actual router decorators: audits=28, incidents=9, risks=13, actions=4, compliance=10, uvdb=14, near_miss=9, rta=13
- Recalculate migration percentages
- **Impacts**: D10, D14

### A5. pr-approval-policy.md
- Replace `ruff` → `flake8`
- Replace `coverage >= 50%` → `--cov-fail-under=43`
- Add missing `all-checks` dependencies: `smoke-gate-selftest`, `config-failfast-proof`, `quality-trend`, `openapi-contract-check`, `audit-acceptance-artifacts`
- Fix `security-scan` tool description: remove `gitleaks` (it's in `secret-scanning`)
- Fix `build-check` description: not "docker build" but Python import check
- **Impacts**: D17

### A6. test-data-strategy.md
- Replace "twelve canonical factories" → "eighteen canonical factories"
- Update factory name table to match actual tests/factories/core.py (TenantFactory not OrganizationFactory, AuditRunFactory/AuditFindingFactory not AuditFactory/AuditSectionFactory, etc.)
- Fix FIXED_EPOCH: string representation vs actual datetime(2026,1,15,10,0,0,tzinfo=timezone.utc)
- Add exception for AuditTemplateFactory's uuid.uuid4() usage or document the factory-level exemption
- **Impacts**: D16

### A7. cost-controls.md
- Replace scale-in "CPU < 40%" → "CPU < 30%" to match autoscale-settings.json threshold: 30
- **Impacts**: D26

### A8. env-parity-verification.md
- Fix Docker base image: `python:3.11-slim` → `python:3.11-slim-bookworm` (match Dockerfile)
- Fix config-drift-guard description: only scans for forbidden legacy strings, NOT schema validation
- Complete verification checklist (check items based on actual repo evidence)
- **Impacts**: D31

### A9. security-review-log.md
- Fix broken link: `docs/security/threat-model.md` → `docs/security/security-baseline.md` (or create threat-model.md per B3)
- **Impacts**: D06

### A10. chaos-testing-plan.md
- Fix broken link: `docs/runbooks/rollback-drills.md` → `docs/runbooks/rollback.md`
- **Impacts**: D05, D23

### A11. a11y-coverage-matrix.md
- Fix broken link: `docs/ux/ux-style-guide.md` → correct path after B1 creates it
- **Impacts**: D03

### A12. usability-testing-results.md
- Fix broken link: `docs/ux/ux-style-guide.md` → correct path after B1 creates it
- **Impacts**: D01

### A13. mypy-reduction-plan.md
- Verify ceiling=190 and count=188 are accurate (they are per verification)
- No changes needed if accurate
- **Impacts**: D21

### A14. locale-coverage.md
- Fix key count: "~56" → "55"
- **Impacts**: D27

---

## Workstream B: Create Missing Files (4 new docs)

### B1. docs/ux/ux-style-guide.md (NEW)
- Design principles, color system (reference design tokens in tailwind.config.js), typography, spacing, component usage guidelines
- Reference existing design-system.md and component-inventory.md
- **Impacts**: D01, D02, D03, D22

### B2. docs/compliance/gdpr-compliance.md (NEW)
- Data processing inventory, lawful basis, DPIA summary, data subject rights, retention schedule, breach notification process
- Reference existing retention-automation-evidence.md
- **Impacts**: D07, D08

### B3. docs/security/threat-model.md (NEW)
- STRIDE-based threat model for the platform
- Attack surface inventory, trust boundaries, key threats and mitigations
- Reference CI security gates from security-review-log.md
- **Impacts**: D06, D22

### B4. docs/runbooks/rollback-drills.md (NEW)
- Consolidate drill evidence from ROLLBACK_DRILL_20260320.md
- Link to rollback.md for procedures
- Document drill schedule and results
- **Impacts**: D05, D23

---

## Workstream C: Fill Templates with Actual Data (4 docs)

### C1. load-test-baseline.md — Run Locust, capture real measurements
- Execute `locust -f tests/performance/locustfile.py` locally against staging (or headless mode)
- Fill measured p50/p95/p99 columns with actual values
- Update test date and environment fields
- **Impacts**: D04, D25

### C2. usability-testing-results.md — Fill baseline results
- Conduct internal walkthrough of core workflows
- Record task completion rates and times
- Fill SUS baseline row with internal-team data (marked as "Internal baseline")
- **Impacts**: D01

### C3. chaos-testing-plan.md — Execute P0 scenarios
- Run P0 scenarios in staging: DB pool exhaustion simulation, Redis unavailability, instance crash recovery
- Document results in the plan or separate evidence file
- **Impacts**: D05

### C4. env-parity-verification.md — Complete checklist
- Verify build SHAs match via `/api/v1/meta/version`
- Verify health endpoints return 200
- Verify migration versions match
- Check all items in the checklist
- **Impacts**: D31

---

## Workstream D: Expand Test Coverage (3 areas)

### D1. Add axe tests for 8 missing routes
- Add to `tests/ux-coverage/tests/a11y-audit.spec.ts` or equivalent:
  `/uvdb`, `/settings`, `/near-misses`, `/rta`, `/policies`, `/compliance`, `/risk-register`, `/import-review`
- Update a11y-coverage-matrix.md to reflect new coverage
- **Impacts**: D03

### D2. Add Welsh translations for critical paths
- Translate at minimum: dashboard, incidents, audits, risks, complaints, actions, settings labels
- Target: 200+ keys (from 55 to 250+) → coverage ~11.5%
- Update locale-coverage.md with new count
- **Impacts**: D27

### D3. Improve backend test coverage
- Add tests for uncovered routes to push toward 50% threshold
- Focus on: findings serialization, risk creation, CAPA generation, UVDB endpoints
- **Impacts**: D15

---

## Workstream E: Fix Inflated Claims in Prior Scorecard (5 corrections)

### E1. test-coverage-baseline.md — ensure accuracy
- Confirm: unit=43%, integration=43%, combined=48%
- Remove any claims of 50%/55%
- **Impacts**: D15

### E2. mypy-reduction-plan.md — ensure accuracy
- Confirm: MAX_TYPE_IGNORES=190 (not 180), count=188, 64 modules ignored (not "5 removed")
- **Impacts**: D21

### E3. Update scorecard to reflect VERIFIED scores
- Create new scorecard with post-fix WCS values
- **Impacts**: D29

---

## Workstream F: Strengthen Remaining Dimensions

### F1. D08 Compliance — expand docs/compliance/
- Add audit trail documentation
- Document policy enforcement via CI gates
- **Impacts**: D08

### F2. D09 Architecture — verify system-diagram.mmd accuracy
- Cross-reference with actual src/ structure
- **Impacts**: D09

### F3. D11/D12 Data model + Schema — verify accuracy of json-column-reduction.md and migration-review-checklist.md
- **Impacts**: D11, D12

### F4. D13 Observability — document backend observability honestly
- Update alerting-rules.md: clearly mark "Active" vs "Planned"
- Ensure correlation-guide accuracy
- **Impacts**: D13

### F5. D18 CD/release — clarify canary-rollout-plan.md
- Distinguish "Current" (slot swap) from "Planned" (canary/traffic split)
- **Impacts**: D18

### F6. D19 Config mgmt — fix config-drift-guard description
- Document actual behavior (forbidden string scanning) vs aspirational (schema validation)
- **Impacts**: D19

### F7. D20 Dependencies — document SBOM artifact workflow
- Note: generated in CI, uploaded as artifact, not committed
- **Impacts**: D20

### F8. D28 Analytics — strengthen telemetry documentation
- Update enablement criteria with concrete dates/steps
- Document staging telemetry evidence
- **Impacts**: D28

### F9. D29 Governance — ensure ADR completeness
- Verify sequential numbering (0001-0010)
- **Impacts**: D29

---

## Summary: Action Count by Workstream

| Workstream | Actions | Dimensions Impacted |
|------------|---------|---------------------|
| A: Fix references | 14 | D05,D06,D10,D14,D16,D17,D23,D24,D26,D27,D30,D31,D32 |
| B: Create files | 4 | D01,D02,D03,D05,D06,D07,D08,D22,D23 |
| C: Fill templates | 4 | D01,D04,D05,D25,D31 |
| D: Expand tests | 3 | D03,D15,D27 |
| E: Fix claims | 3 | D15,D21,D29 |
| F: Strengthen dims | 9 | D08,D09,D11,D12,D13,D18,D19,D20,D28,D29 |
| **Total** | **37** | **All 32 dimensions** |
