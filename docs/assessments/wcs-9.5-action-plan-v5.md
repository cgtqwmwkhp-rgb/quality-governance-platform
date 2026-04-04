# WCS 9.5 Action Plan — v5

**Generated:** 2026-04-03
**Blueprint:** `wcs-9.5-blueprint-v5.md`
**Review findings incorporated:** F-01 through F-20 (6 CRITICAL, 5 HIGH, 6 MEDIUM, 3 LOW)

---

## Execution Strategy

**8 Phases**, strictly sequential. Each phase must pass `make pr-ready` before proceeding.

### Key Review Finding Mitigations (F-01 through F-11)

| Finding | Mitigation in this plan |
|---------|------------------------|
| F-01 (DomainError API) | Use existing subclasses (NotFoundError, ConflictError, etc.) — no status_code param needed |
| F-02 (CAPA Enum duplication) | Skip CheckConstraints for models using SQLAlchemy Enum() types |
| F-03 (65 ignore_errors modules) | Added Phase 7: mypy reduction workstream |
| F-04 (Auto-rollback is docs-only) | Phase 4: implement actual `az webapp deployment slot swap` with `if: failure()` |
| F-05 (Coverage 48→55% unbacked) | Phase 6: measure first, add tests, raise threshold only after validation |
| F-06 (Locust p95 200ms breaks CI) | Changed: keep 500ms CI threshold, document 200ms as production SLO separately |
| F-07 (Single migration risk) | Phase 3: split into 2 migrations with NOT VALID + VALIDATE |
| F-08 (Error migration breaks contract) | Phase 5: error_handler.py already normalizes; verify frontend parses both |
| F-09 (50+ TBD docs) | Phase 8: comprehensive TBD sweep across ALL docs |
| F-10 (CI job phasing) | Phase 2: add new jobs as advisory first; Phase 2B: promote to blocking |
| F-11 (risk_score bounds) | Phase 3: use BETWEEN 1 AND 25 for risk_score |

---

## Phase 1: CI Unblockers + Date Fixes (MUST DO FIRST)

**Risk:** CI currently FAILS if compliance-freshness gate runs. Fix before any other changes.

| # | Action | File | Change |
|---|--------|------|--------|
| 1.1 | Fix compliance date | `docs/compliance/compliance-matrix-iso.md` | Replace `_[YYYY-MM-DD]_` with `2026-04-03` |
| 1.2 | Fix security date | `docs/security/security-policy.md` | Replace `_[YYYY-MM-DD]_` with `2026-04-03` |
| 1.3 | Fix runtime config date | `docs/ops/runtime-config-inventory.md` | Replace `_[YYYY-MM-DD]_` with `2026-04-03` |
| 1.4 | Fix retention date | `docs/privacy/data-retention-policy.md` | Replace `_[YYYY-MM-DD]_` with `2026-04-03` |
| 1.5 | Fix DPIA date | `docs/privacy/dpia-template.md` | Replace `_[YYYY-MM-DD]_` with `2026-04-03` |
| 1.6 | Fix DPIA method name | `docs/privacy/dpia-incidents.md` | Change `data_portability_export()` to `export_user_data()` |

**Verification:** `grep -r '_\[YYYY-MM-DD\]_' docs/` returns 0 matches.
**Dimensions:** D08, D07, D22

---

## Phase 2: CI/CD Hardening (Advisory Phase)

**Strategy (per F-10):** Add new jobs as ADVISORY first (not in all-checks). Promote in Phase 2B.

| # | Action | File | Detail |
|---|--------|------|--------|
| 2.1 | Add `radon-complexity` job | `ci.yml` | `radon cc src/ -a -nc`; threshold: average CC grade B or better. NOT in all-checks yet |
| 2.2 | Add `alembic-check` job | `ci.yml` | `alembic check`; NOT in all-checks yet |
| 2.3 | Promote TTI to error | `lighthouserc.json` | Change `interactive` from warn to error |
| 2.4 | Expand Lighthouse URLs | `lighthouserc.json` | Add `/incidents`, `/audits`, `/risks`, `/complaints`, `/actions` |
| 2.5 | Remove `\|\| true` from mutation | `ci.yml` | Lines 1469, 1473, 1474; allow failure reporting (stays schedule-only) |
| 2.6 | Convert ErrorCode to Enum | `src/api/schemas/error_codes.py` | Change `class ErrorCode:` to `class ErrorCode(str, Enum):` (per F-12) |
| 2.7 | Add ISO8601 validation | `scripts/governance/validate_release_signoff.py` | Add `datetime.fromisoformat(approved_at_utc)` validation |
| 2.8 | Make doc link check blocking | `ci.yml` docs-lint job | Remove `\|\| echo "::warning::"` from markdown-link-check step |
| 2.9 | Add compliance-freshness expansion | `ci.yml` | Add `data-retention-policy.md` and `dpia-template.md` to the checked files |

**Phase 2B (after validation):**

| # | Action | Condition |
|---|--------|-----------|
| 2B.1 | Add `radon-complexity` to all-checks | After 1 clean run |
| 2B.2 | Add `alembic-check` to all-checks | After 1 clean run |

**Dimensions:** D04, D12, D15, D17, D21, D29

---

## Phase 3: Data Model Constraints

**Strategy (per F-07):** Split into 2 Alembic migrations. Use NOT VALID then VALIDATE.
**Strategy (per F-02):** Skip models using SQLAlchemy Enum() types (only capa.py).
**Strategy (per F-11):** Use `BETWEEN 1 AND 25` for computed scores.

### Migration 1: Integer range constraints

| # | Model File | Table | Constraints |
|---|-----------|-------|-------------|
| 3.1 | `risk.py` | `risks` | `likelihood BETWEEN 1 AND 5`, `impact BETWEEN 1 AND 5`, `risk_score BETWEEN 1 AND 25` |
| 3.2 | `risk.py` | `risk_assessments` | `inherent_likelihood BETWEEN 1 AND 5`, `inherent_impact BETWEEN 1 AND 5`, `inherent_score BETWEEN 1 AND 25`, same for residual_* |
| 3.3 | `risk_register.py` | `enterprise_risks` | `inherent_likelihood BETWEEN 1 AND 5`, `inherent_impact BETWEEN 1 AND 5`, `effectiveness_score BETWEEN 1 AND 5` |
| 3.4 | `risk_register.py` | `risk_scenarios` | `inherent_likelihood BETWEEN 1 AND 5`, `inherent_impact BETWEEN 1 AND 5` |
| 3.5 | `kri.py` | KRI table | `threshold_value >= 0` (if column exists as Integer) |
| 3.6 | `document_control.py` | controlled_documents | `version >= 1` (if version is Integer) |
| 3.7 | `workflow.py` | workflows | `version >= 1` |

### Migration 2: String/status constraints

| # | Model File | Table | Constraints |
|---|-----------|-------|-------------|
| 3.8 | `rta.py` | `road_traffic_collisions` | `severity IN ('minor','damage_only','injury','fatal')` |
| 3.9 | `digital_signature.py` | signatures table | `status IN ('pending','signed','rejected','expired')` |
| 3.10 | `iso27001.py` | security assets | `confidentiality_impact BETWEEN 1 AND 3`, `integrity_impact BETWEEN 1 AND 3`, `availability_impact BETWEEN 1 AND 3` |

**Approach for both migrations:**
1. Add constraints in model `__table_args__`
2. In Alembic migration, use `ALTER TABLE ... ADD CONSTRAINT ... NOT VALID` for safety
3. Follow with `ALTER TABLE ... VALIDATE CONSTRAINT ...` to verify existing data

**Dimensions:** D11, D24, D08

---

## Phase 4: Reliability & CD Hardening

**Strategy (per F-04):** Implement actual rollback, not documentation.

| # | Action | File | Detail |
|---|--------|------|--------|
| 4.1 | Add auto-rollback job | `deploy-production.yml` | New `auto-rollback` job with `if: failure() && needs.build-and-deploy.result == 'failure'`; executes `az webapp deployment slot swap --resource-group $RG --name $APP --slot staging --target-slot production` |
| 4.2 | Add post-deploy smoke blocking | `deploy-production.yml` | Keep `continue-on-error: true` on E2E (per F-17 — E2E secrets may not be set), but add a separate non-E2E smoke check (healthz + readyz + version) as blocking |
| 4.3 | Document chaos test results | `docs/evidence/chaos-testing-plan.md` | Update 3 verified scenarios with actual timestamps and outcomes |
| 4.4 | Document RTO/RPO | `docs/evidence/chaos-testing-plan.md` | Add section: RTO = 8s (slot swap), RPO = 0 (same DB) based on actual drill data |
| 4.5 | Add retention rules | `src/infrastructure/tasks/cleanup_tasks.py` | Add rules for incidents (365d), complaints (365d), rtas (365d), near_misses (365d), investigations (365d) |
| 4.6 | Add restrict_processing method | `src/domain/services/gdpr_service.py` | Art. 18 stub: mark records as restricted; filter in queries |

**Dimensions:** D05, D07, D08, D18

---

## Phase 5: Error Migration (Top 15 Route Files)

**Strategy (per F-01):** Use existing DomainError subclasses:
- 404 → `raise NotFoundError("message")`
- 409 → `raise ConflictError("message")`
- 422 → `raise ValidationError("message")`
- 401 → `raise AuthenticationError("message")`
- 403 → `raise AuthorizationError("message")`
- 400 → `raise ValidationError("message")` (map 400 to ValidationError)
- 500 → keep as HTTPException or use DomainError base

**Strategy (per F-08):** The existing `error_handler.py` already normalizes both DomainError AND HTTPException into the same envelope format, so the response contract won't break.

| # | File | HTTPException Count | Priority |
|---|------|---------------------|----------|
| 5.1 | `audits.py` | 24 | High |
| 5.2 | `investigations.py` | 23 | High |
| 5.3 | `actions.py` | 22 | High |
| 5.4 | `inductions.py` | 22 | High |
| 5.5 | `assessments.py` | 22 | High |
| 5.6 | `form_config.py` | 21 | High |
| 5.7 | `evidence_assets.py` | 20 | High |
| 5.8 | `risk_register.py` | 18 | High |
| 5.9 | `vehicle_checklists.py` | 16 | Medium |
| 5.10 | `users.py` | 15 | Medium |
| 5.11 | `incidents.py` | 13 | Medium |
| 5.12 | `complaints.py` | 12 | Medium |
| 5.13 | `workflow.py` | 12 | Medium |
| 5.14 | `standards.py` | 12 | Medium |
| 5.15 | `tenants.py` | 11 | Medium |

**Pattern for each file:**
```python
# BEFORE:
raise HTTPException(status_code=404, detail="Risk not found")
# AFTER:
raise NotFoundError("Risk not found")

# BEFORE:
raise HTTPException(status_code=400, detail="Invalid score")
# AFTER:
raise ValidationError("Invalid score")
```

**Dimensions:** D10, D14

---

## Phase 6: Testing & Frontend Quality

**Strategy (per F-05):** Measure coverage FIRST, then add tests, then raise threshold.

| # | Action | File | Detail |
|---|--------|------|--------|
| 6.1 | Measure current coverage | N/A | Run `pytest --cov=src --cov-report=term-missing`; record baseline |
| 6.2 | Create factory validation test | `tests/unit/test_factory_build_validation.py` | Test all 18 factories `.build()` produces valid instances |
| 6.3 | Add golden fixtures | `tests/fixtures/golden/` | Add `driver.json`, `vehicle.json`, `engineer.json`, `kri.json`, `signature.json` |
| 6.4 | Tighten CUJ-02 | `tests/e2e/test_cuj02_capa_from_incident.py` | Assert `source_id == incident_id` |
| 6.5 | Tighten CUJ-03 | `tests/e2e/test_cuj03_daily_vehicle_checklist.py` | Add checklist completion flow |
| 6.6 | Tighten CUJ-06 | `tests/e2e/test_cuj06_evidence_upload.py` | Verify asset linked after upload |
| 6.7 | Update traceability matrix | `docs/user-journeys/cuj-test-traceability.md` | Move CUJs 02, 03, 06 from "Gap" to "Covered" |
| 6.8 | Raise coverage to 52% | `pyproject.toml` + `ci.yml` | Intermediate step (per F-05): 48→52%, verify passes |
| 6.9 | Install Storybook packages | `frontend/package.json` | `npm install -D @storybook/react-vite @storybook/addon-essentials @storybook/react storybook` |
| 6.10 | Create 22 component stories | `frontend/src/components/ui/*.stories.tsx` | One story file per component with default + variants |
| 6.11 | Add axe tests for 6 components | `frontend/src/components/__tests__/*.a11y.test.tsx` | ThemeToggle, SetupRequiredPanel, LoadingSkeleton, SkeletonLoader, LiveAnnouncer, Textarea |

**Dimensions:** D01, D02, D03, D15, D16

---

## Phase 7: Type Safety & Code Quality (per F-03)

**Strategy:** Remove easy modules from `ignore_errors`, add ratchet.

| # | Action | File | Detail |
|---|--------|------|--------|
| 7.1 | Audit 65 modules for fix difficulty | N/A | Run `mypy` on each module individually to count errors |
| 7.2 | Remove 15 easiest modules from ignore list | `pyproject.toml` | Target modules with <5 mypy errors each |
| 7.3 | Add type stubs or annotations | Various | Fix type errors in removed modules |
| 7.4 | Lower MAX_TYPE_IGNORES by 10 | `scripts/validate_type_ignores.py` | From 190 → 180 |
| 7.5 | Add mypy module ratchet CI check | `ci.yml` | Count modules with `ignore_errors` and fail if increased |

**Dimensions:** D15, D17, D21

---

## Phase 8: Documentation & Governance Sweep

**Strategy (per F-09):** Comprehensive TBD/PLACEHOLDER sweep across ALL docs.

| # | Action | File | Detail |
|---|--------|------|--------|
| 8.1 | Fill capacity plan TBDs | `docs/infra/capacity-plan.md` | Replace all "TBD" with estimated values |
| 8.2 | Fill cost/capacity runbook | `docs/ops/COST_CAPACITY_RUNBOOK.md` | Replace "TBD — from Azure metrics" |
| 8.3 | Fill DR runbook placeholders | `docs/ops/DISASTER_RECOVERY_RUNBOOK.md` | Replace `[PLACEHOLDER]` with actual contact info |
| 8.4 | Fill deployment runbook | `docs/DEPLOYMENT_RUNBOOK.md` | Replace `[TBD]` for owner/DBA/DevOps |
| 8.5 | Add unit economics | `docs/infra/cost-controls.md` | Per-tenant cost breakdown section |
| 8.6 | Create ADR-0011 | `docs/adr/ADR-0011-api-versioning-strategy.md` | Document `/api/v1/` prefix versioning decision |
| 8.7 | Create ADR-0012 | `docs/adr/ADR-0012-testing-strategy.md` | Document test pyramid, coverage targets, mutation testing |
| 8.8 | Add DORA metrics doc | `docs/governance/dora-metrics.md` | Lead time, deploy frequency, MTTR, change failure rate |
| 8.9 | Update DPIA consultation | `docs/privacy/dpia-incidents.md` | Mark internal stakeholders as "Reviewed (internal)" |
| 8.10 | Fill WCAG checklist TBDs | `docs/accessibility/wcag-checklist.md` | Verify 1.4.11, 2.5.3, 3.3.3 criteria |
| 8.11 | Fill pentest plan TBD | `docs/security/pentest-plan.md` | Set internal review schedule |
| 8.12 | Fill rollback drill TBD | `docs/runbooks/rollback-drills.md` | PostgreSQL PITR drill planned date |
| 8.13 | Add env-vars registry | `scripts/infra/env-vars.json` | Central registry of all env vars |
| 8.14 | Make i18n threshold blocking | `scripts/i18n-check.mjs` | Wire `cyBelowThreshold` to `process.exit(1)` |
| 8.15 | Add 200+ Welsh translations | `frontend/src/i18n/locales/cy.json` | Target 80%+ coverage |
| 8.16 | Remove orphan Welsh keys | `frontend/src/i18n/locales/cy.json` | Remove 87 keys not in en.json |
| 8.17 | Wire track_metric to 15 more routes | `src/api/routes/*.py` | Wire remaining defined-but-unwired instruments |
| 8.18 | Add /diagnostics endpoint | `src/api/routes/health.py` | Admin-only; returns config, flags, OTel status, migration head; redact secrets (per F-15) |
| 8.19 | Add admin CLI commands | `scripts/admin_cli.py` | Add `logs` and `cache-stats` commands |
| 8.20 | Activate planned alerts | `docs/observability/alerting-rules.md` | Change 7 "Planned" alerts to "Active" with thresholds |
| 8.21 | Document production SLO | `docs/performance/api-slos.md` | p95 < 200ms target (NOT in CI gate per F-06) |
| 8.22 | Expand config-drift-guard | `ci.yml` | Add env-var key comparison between .env.example and Settings class |

**Dimensions:** D01, D13, D19, D22, D23, D25, D26, D27, D28, D29, D31, D32

---

## Phase Sequencing & Dependencies

```
Phase 1 (CI Unblockers)
   ↓
Phase 2 (CI Hardening — advisory)
   ↓
Phase 3 (Data Model Constraints)
   ↓
Phase 4 (Reliability & Privacy)
   ↓
Phase 5 (Error Migration)
   ↓
Phase 6 (Testing & Frontend)
   ↓
Phase 7 (Type Safety)
   ↓
Phase 8 (Documentation & Governance Sweep)
   ↓
Phase 2B (Promote advisory CI jobs to blocking)
```

**Critical dependency:** Phase 1 MUST complete before any PR merge.
**Cross-dependency:** Phase 2B depends on clean Phase 2 runs.
**Parallel-safe:** Phases 6 and 7 could run in parallel if needed.

---

## Verification Criteria

After all phases:

| Check | Command | Expected |
|-------|---------|----------|
| No placeholder dates | `grep -r '_\[YYYY-MM-DD\]_' docs/` | 0 matches |
| CI passes | `make pr-ready` | Exit 0 |
| CheckConstraints exist | `grep -r 'CheckConstraint' src/domain/models/ \| wc -l` | >= 20 |
| Error migration progress | `grep -r 'raise HTTPException' src/api/routes/ \| wc -l` | < 260 (down from 458) |
| Storybook stories | `ls frontend/src/components/ui/*.stories.tsx \| wc -l` | >= 26 |
| Welsh coverage | `node scripts/i18n-check.mjs` | >= 80% |
| Factory validation | `pytest tests/unit/test_factory_build_validation.py` | Pass |
| mypy modules reduced | Count modules in ignore_errors block | < 55 |
| Coverage threshold | `pytest --cov-fail-under=52` | Pass |

---

## Risk Register (Updated from Blueprint Review)

| Risk | Impact | Mitigation |
|------|--------|------------|
| CheckConstraint violates existing data | High | NOT VALID clause + VALIDATE CONSTRAINT |
| Locust threshold too aggressive | HIGH → MITIGATED | Keep 500ms in CI; document 200ms as prod SLO (F-06) |
| DomainError API wrong | HIGH → MITIGATED | Use existing subclasses, not status_code param (F-01) |
| CAPA constraint conflicts with Enum | HIGH → MITIGATED | Skip CAPA; it uses SQLAlchemy Enum (F-02) |
| Coverage raise breaks CI | HIGH → MITIGATED | Measure first; intermediate 52% target (F-05) |
| Error migration breaks frontend | MEDIUM | error_handler.py normalizes both; check frontend parses new format |
| New CI jobs block all PRs | MEDIUM | Advisory phase first (F-10) |
| Welsh translations low quality | LOW | Mark as "machine-translated, pending review" |
| Storybook install breaks build | LOW | devDependency only |
