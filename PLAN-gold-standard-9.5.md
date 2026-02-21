# Gold Standard 9.5+ Platform Plan

**Created:** 2026-02-20
**Objective:** Bring all 23 dimensions to 9.5+ by closing the 8 remaining gaps with surgical, high-impact changes.
**Current Average:** 8.83/10 | **Target Average:** 9.5+/10

---

## Revised Baseline (with corrections)

| # | Dimension | Current | Target | Delta |
|---|-----------|---------|--------|-------|
| 1 | Auth & Authorization | 9.0 | 9.0 | — |
| 2 | Token Management | 10.0 | 10.0 | — |
| 3 | Security Headers | 10.0 | 10.0 | — |
| 4 | Secrets Management | 10.0 | 10.0 | — |
| 5 | Multi-Tenant Isolation | 9.0 | 9.0 | — |
| 6 | API Consistency | 9.0 | 9.0 | — |
| 7 | Input Validation & Typing | 9.0 | 9.0 | — |
| 8 | Error Handling | 10.0 | 10.0 | — |
| 9 | Architecture (Service Layer) | 9.0 | 9.0 | — |
| 10 | Dependency Injection | 10.0 | 10.0 | — |
| 11 | **Unit Tests** | **7.0** | **9.5** | **+2.5** |
| 12 | **E2E Tests** | **8.0** | **9.5** | **+1.5** |
| 13 | **Test Infrastructure** | **8.0** | **9.5** | **+1.5** |
| 14 | CI/CD Pipeline | 9.0 | 9.5 | +0.5 |
| 15 | Database & ORM | 9.0 | 9.0 | — |
| 16 | **Caching** | **8.0** | **9.5** | **+1.5** |
| 17 | **Background Tasks** | **8.0** | **9.5** | **+1.5** |
| 18 | Infrastructure (Docker) | 9.0 | 9.0 | — |
| 19 | React Architecture | 9.0 | 9.5 | +0.5 |
| 20 | **Frontend Build** | **8.0** | **9.5** | **+1.5** |
| 21 | **UI/UX Quality** | **8.0** | **9.5** | **+1.5** |
| 22 | **Observability** | **8.0** | **9.5** | **+1.5** |
| 23 | Documentation | 9.0 | 9.5 | +0.5 |

**Corrections from initial audit:**
- Dark mode EXISTS (ThemeContext.tsx with system preference detection) — was incorrectly flagged
- Redis fallback to InMemoryCache EXISTS (after 3 consecutive failures) — was incorrectly flagged
- Keyboard shortcuts PARTIALLY exist (Cmd+K search, Ctrl+S save, Escape handlers)

---

## PHASE 1: Testing Transformation (Dimensions 11, 12, 13) — HIGHEST IMPACT

### Task 1.1: Upgrade 20 Frontend Smoke Tests to Real Tests
**Dimension:** 11 (Unit Tests) | **Impact:** HIGH

Replace `expect(document.body).toBeTruthy()` with real element queries and interactions in these 20 files:

1. `frontend/tests/unit/pages/RTADetail.test.tsx`
2. `frontend/tests/unit/pages/PortalTrack.test.tsx`
3. `frontend/tests/unit/pages/PortalReport.test.tsx`
4. `frontend/tests/unit/pages/PortalRTAForm.test.tsx`
5. `frontend/tests/unit/pages/PortalNearMissForm.test.tsx`
6. `frontend/tests/unit/pages/PortalLogin.test.tsx`
7. `frontend/tests/unit/pages/PortalIncidentForm.test.tsx`
8. `frontend/tests/unit/pages/PortalHelp.test.tsx`
9. `frontend/tests/unit/pages/PortalDynamicForm.test.tsx`
10. `frontend/tests/unit/pages/Portal.test.tsx`
11. `frontend/tests/unit/pages/Login.test.tsx`
12. `frontend/tests/unit/pages/FormsList.test.tsx`
13. `frontend/tests/unit/pages/FormBuilder.test.tsx`
14. `frontend/tests/unit/pages/ForgotPassword.test.tsx`
15. `frontend/tests/unit/pages/ExportCenter.test.tsx`
16. `frontend/tests/unit/pages/ContractsManagement.test.tsx`
17. `frontend/tests/unit/pages/ComplianceEvidence.test.tsx`
18. `frontend/tests/unit/pages/AdminDashboard.test.tsx`
19. `frontend/tests/unit/pages/AIIntelligence.test.tsx`
20. `frontend/tests/unit/pages/MobileAuditExecution.test.tsx`
21. `frontend/tests/unit/pages/ComplianceAutomation.test.tsx`

**What each test should verify:**
- Component renders without crashing (keep this)
- Key UI elements are present (headings, buttons, tables)
- Loading states render correctly (skeleton loaders)
- User interactions trigger expected behavior (click handlers, form inputs)
- Error states are handled

### Task 1.2: Write Backend Service Tests for Top 15 Critical Services
**Dimension:** 11 (Unit Tests) | **Impact:** HIGH

33 of 37 services have zero tests. Prioritize by business criticality:

**Tier 1 — Core business (must test):**
1. `src/domain/services/workflow_engine.py` → `tests/unit/test_workflow_engine_service.py`
2. `src/domain/services/audit_scoring_service.py` → `tests/unit/test_audit_scoring_service.py`
3. `src/domain/services/risk_scoring.py` → `tests/unit/test_risk_scoring_service.py`
4. `src/domain/services/risk_statistics_service.py` → `tests/unit/test_risk_statistics_service.py`
5. `src/domain/services/compliance_automation_service.py` → `tests/unit/test_compliance_automation_service.py`

**Tier 2 — Important integration (should test):**
6. `src/domain/services/notification_service.py` → `tests/unit/test_notification_service.py`
7. `src/domain/services/signature_service.py` → `tests/unit/test_signature_service.py`
8. `src/domain/services/kri_calculation_service.py` → `tests/unit/test_kri_calculation_service.py`
9. `src/domain/services/tenant_service.py` → `tests/unit/test_tenant_service.py`
10. `src/domain/services/email_service.py` → `tests/unit/test_email_service.py`

**Tier 3 — Supporting services:**
11. `src/domain/services/workflow_calculation_service.py` → `tests/unit/test_workflow_calculation_service.py`
12. `src/domain/services/risk_register_service.py` → `tests/unit/test_risk_register_service.py`
13. `src/domain/services/copilot_service.py` → `tests/unit/test_copilot_service.py`
14. `src/domain/services/analytics_service.py` → `tests/unit/test_analytics_service.py`
15. `src/domain/services/document_ai_service.py` → `tests/unit/test_document_ai_service.py`

**Each test file should contain:**
- Pure function tests (no DB required) for calculation/scoring logic
- Mock-based tests for DB-dependent methods
- Edge case coverage (empty inputs, boundary values, invalid data)
- Minimum 5 test cases per service

### Task 1.3: Replace Always-Pass E2E Assertions
**Dimension:** 12 (E2E Tests) | **Impact:** MEDIUM

Replace these 3 trivial assertions with real checks:

1. `frontend/tests/e2e/user-management.spec.ts` line 74: `expect(true).toBeTruthy()`
   → Replace with actual DOM element check
2. `frontend/tests/e2e/staging-verification.spec.ts` line 118: `expect(true).toBe(true)`
   → Replace with response status or content check
3. `frontend/tests/e2e/staging-verification.spec.ts` line 272: `expect(true).toBe(true)`
   → Replace with actual console error check

### Task 1.4: Raise Coverage Thresholds
**Dimension:** 11, 13 (Unit Tests, Test Infrastructure) | **Impact:** HIGH

After adding the new tests:

**Frontend (`vitest.config.ts`):**
- Statements: 45% → 55%
- Branches: 30% → 40%
- Functions: 15% → 25%
- Lines: 45% → 55%

**Backend (`ci.yml`):**
- Unit tests: 45% → 55%
- Integration tests: 45% → 55%

Update `CONTRIBUTING.md` to match new thresholds.

### Task 1.5: Stabilize CI Test Infrastructure
**Dimension:** 13, 14 (Test Infrastructure, CI/CD) | **Impact:** HIGH

**Root cause of CI flakiness:** Integration/smoke/E2E jobs require PostgreSQL but NOT Redis or Celery workers. Tests that touch cache or async tasks fail.

**Fixes:**
1. Add Redis service to integration-tests, smoke-tests, and e2e-tests jobs in `ci.yml`
2. Add explicit DB readiness wait after Alembic migrations
3. Un-quarantine `tests/integration/conftest.py` core fixtures:
   - `auth_headers` → Use test JWT generation
   - `test_session` → Configure async test DB session
4. Fix API contract mismatches in E2E tests (e.g., `/api/portal/report` → `/api/portal/reports/`)

---

## PHASE 2: Operational Maturity (Dimensions 16, 17, 22)

### Task 2.1: Cache Hit Rate Metrics + Circuit Breaker Enhancement
**Dimension:** 16 (Caching) | **Impact:** MEDIUM

In `src/infrastructure/cache/redis_cache.py`:
1. Calculate and expose `hit_rate` percentage from Redis INFO stats (`keyspace_hits / (keyspace_hits + keyspace_misses)`)
2. Add `track_metric("cache.hit_rate", hit_rate)` call
3. Enhance the existing fallback pattern with an auto-recovery timer (attempt Redis reconnection every 60s when in fallback mode)

### Task 2.2: DLQ Alerting + Replay Mechanism
**Dimension:** 17 (Background Tasks) | **Impact:** MEDIUM

1. In `src/infrastructure/tasks/dlq.py`:
   - Add `track_metric("dlq.size", count)` after each failed task insertion
   - Add periodic DLQ size check in Celery beat schedule
2. In `src/infrastructure/monitoring/alerts.py`:
   - Add `dlq_growth` alert rule (threshold: >5 failed tasks in 1 hour)
3. Create `src/infrastructure/tasks/dlq_replay.py`:
   - Celery task that retries un-retried DLQ entries (max 1 retry per entry)
   - Add to beat schedule (run every 6 hours)

### Task 2.3: SLO/SLI Definitions + Trace Sampling
**Dimension:** 22 (Observability) | **Impact:** MEDIUM

1. Create `docs/SLO-SLI.md` defining:
   - API availability SLO: 99.9% uptime
   - API latency SLI: P95 < 500ms, P99 < 2s
   - Error rate SLI: < 0.1% 5xx responses
   - Deployment success SLI: > 95% deployments without rollback
2. In `src/infrastructure/monitoring/azure_monitor.py`:
   - Add `TraceIdRatioBased` sampler: 100% in staging, 10% in production
   - Make sampling rate configurable via `OTEL_TRACE_SAMPLE_RATE` env var

---

## PHASE 3: Frontend Polish (Dimensions 20, 21)

### Task 3.1: Web Vitals Integration
**Dimension:** 20 (Frontend Build) | **Impact:** MEDIUM

1. Install `web-vitals` package
2. Create `frontend/src/utils/web-vitals.ts`:
   - Track CLS, FID, LCP, FCP, TTFB
   - Report to console in development, POST to `/api/telemetry/web-vitals` in production
3. Initialize in `frontend/src/main.tsx`

### Task 3.2: Replace Remaining Loader2 on High-Traffic Pages
**Dimension:** 21 (UI/UX Quality) | **Impact:** MEDIUM

Target the 4 pages with heaviest Loader2 usage for primary loading states:
1. `InvestigationDetail.tsx` (17 Loader2 instances) — replace primary page load spinner with skeleton
2. `AuditTemplateBuilder.tsx` (11 instances) — replace section loading spinners with skeletons
3. `MobileAuditExecution.tsx` (8 instances) — replace main load with skeleton
4. `ComplianceAutomation.tsx` (7 instances) — replace table loading with TableSkeleton

*Note: Keep Loader2 for button-loading and inline action states — that's appropriate UX.*

### Task 3.3: Centralized Keyboard Shortcut System
**Dimension:** 21 (UI/UX Quality) | **Impact:** LOW-MEDIUM

1. Create `frontend/src/hooks/useKeyboardShortcuts.ts`:
   - Register/unregister shortcuts with descriptions
   - Conflict detection
   - `?` key opens shortcut help overlay
2. Create `frontend/src/components/KeyboardShortcutHelp.tsx`:
   - Modal listing all registered shortcuts
3. Register existing shortcuts (Cmd+K, Ctrl+S, Escape) through the centralized system
4. Add `Cmd+/` → toggle sidebar, `G then D` → go to dashboard, `G then I` → go to incidents

---

## PHASE 4: Documentation + Final Polish (Dimensions 14, 19, 23)

### Task 4.1: Document Global Entity Tenant Exemptions
**Dimension:** 23 (Documentation) | **Impact:** LOW

Add a section to `docs/ARCHITECTURE.md` documenting which entities are intentionally tenant-agnostic (Standard, Clause, Control, Role) and why they don't require `tenant_id` in `get_or_404` calls.

### Task 4.2: Create ADR for Testing Strategy
**Dimension:** 23 (Documentation) | **Impact:** LOW

Create `docs/adr/ADR-0016-testing-strategy.md`:
- Unit test philosophy (real assertions, no smoke-only)
- Coverage threshold rationale and progression targets
- Service test patterns (pure logic vs mock-based)
- E2E test standards (no always-pass assertions)

---

## Implementation Order

| Round | Tasks | Est. Files Changed | Est. Lines Added |
|-------|-------|-------------------|-----------------|
| 1 | 1.1, 1.3 | ~24 | ~1,200 |
| 2 | 1.2 | ~15 | ~1,500 |
| 3 | 1.4, 1.5 | ~8 | ~200 |
| 4 | 2.1, 2.2, 2.3 | ~8 | ~400 |
| 5 | 3.1, 3.2, 3.3 | ~12 | ~600 |
| 6 | 4.1, 4.2 | ~3 | ~200 |

**Total: ~70 files, ~4,100 lines**

---

## Expected Outcome

| # | Dimension | Before | After |
|---|-----------|--------|-------|
| 11 | Unit Tests | 7.0 | 9.5 |
| 12 | E2E Tests | 8.0 | 9.5 |
| 13 | Test Infrastructure | 8.0 | 9.5 |
| 14 | CI/CD Pipeline | 9.0 | 9.5 |
| 16 | Caching | 8.0 | 9.5 |
| 17 | Background Tasks | 8.0 | 9.5 |
| 19 | React Architecture | 9.0 | 9.5 |
| 20 | Frontend Build | 8.0 | 9.5 |
| 21 | UI/UX Quality | 8.0 | 9.5 |
| 22 | Observability | 8.0 | 9.5 |
| 23 | Documentation | 9.0 | 9.5 |

**Projected Overall Average: 9.5/10** (all dimensions at 9.0 or above, 8 dimensions elevated)
