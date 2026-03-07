# Top 15 Focus Areas — World-Class Uplift Action Plan

**Date**: 2026-03-07
**Current Average WCS**: 7.1 / 10.0
**Target**: 9.5+

---

## Tier 1: Low Effort / High Value (execute immediately)

### 1. Close the last 3 unauthenticated route modules (D06 → +0.5 WCS)

**Gap**: `planet_mark.py` (16 endpoints), `uvdb.py` (12 endpoints), and `slo.py` (2 endpoints) have zero auth guards. Business-sensitive carbon, UVDB audit, and SLO metrics data exposed to anyone.

**What to change**:
- `src/api/routes/planet_mark.py` — add `from src.api.dependencies import CurrentUser` and add `current_user: CurrentUser` parameter to all 16 endpoint functions. Add `tenant_id` filtering to all DB queries.
- `src/api/routes/uvdb.py` — same pattern for all 12 endpoints.
- `src/api/routes/slo.py` — add `CurrentUser` to `/slo/current` and `/slo/metrics`.
- Update `tests/unit/test_auth_enforcement.py` to verify these 3 modules.

**Definition of Done**: All 61 route modules return 401 without token. Auth enforcement test covers 61/61.
**Effort**: S | **Value**: H | **Expected lift**: D06 8.0 → 8.5

---

### 2. Add Content-Security-Policy header (D06 → +0.3 WCS)

**Gap**: `SecurityHeadersMiddleware` in `src/main.py` sets 8 security headers but no CSP. XSS mitigation incomplete.

**What to change**:
- `src/main.py` lines 22-43 — add to the `SecurityHeadersMiddleware`:
  ```python
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      "script-src 'self'; "
      "style-src 'self' 'unsafe-inline'; "
      "img-src 'self' data: https:; "
      "font-src 'self'; "
      "connect-src 'self' https://*.azurewebsites.net https://*.azurestaticapps.net; "
      "frame-ancestors 'none'; "
      "base-uri 'self'; "
      "form-action 'self'"
  )
  ```

**Definition of Done**: CSP header present on all API responses; frontend loads without CSP violations.
**Effort**: S | **Value**: H | **Expected lift**: D06 8.0 → 8.3

---

### 3. Add toast notification system (D02, D14 → +0.8 WCS)

**Gap**: No toast/notification system for mutation feedback. Users get no visible confirmation when creating incidents, saving audits, or updating risks. Errors are caught but never shown.

**What to change**:
- `npm install sonner` in `frontend/`
- `frontend/src/App.tsx` — add `<Toaster />` component at root
- `frontend/src/api/client.ts` — add `toast.error(classifiedMessage)` in error interceptor; add `toast.success()` helper
- Wrap mutation calls in key pages (incidents, complaints, audits, risks) with `toast.success("Incident created")` on success

**Definition of Done**: All create/update/delete operations show toast feedback; errors show descriptive toast.
**Effort**: S | **Value**: H | **Expected lift**: D02 5.4 → 6.2, D14 8.0 → 8.3

---

### 4. Add Skeleton loading component + replace spinners (D02, D04 → +0.6 WCS)

**Gap**: All loading states show a plain `Loader2` spinner. No content-shaped skeletons. Perceived performance is poor. Component inventory identifies Skeleton as high-priority missing component.

**What to change**:
- Create `frontend/src/components/ui/Skeleton.tsx` — simple div with `animate-pulse bg-muted rounded` styling
- Create `frontend/src/components/ui/TableSkeleton.tsx` — skeleton rows for list views
- Replace `<Loader2>` with skeleton in `Dashboard.tsx`, `Incidents.tsx`, `Complaints.tsx`, `Risks.tsx`, `Audits.tsx`

**Definition of Done**: 5 key pages show content-shaped skeletons during load instead of spinners.
**Effort**: S | **Value**: H | **Expected lift**: D02 5.4 → 6.0, D04 5.4 → 5.7

---

### 5. Wire Dashboard to real API data (D01, D02, D28 → +1.2 WCS)

**Gap**: Dashboard shows hardcoded 0 for RTAs, complaints, audits, actions, risks, compliance, carbon. Notification badge hardcoded to 5. Activity feed and upcoming events are empty arrays. Only `incidentsApi.list()` is connected.

**What to change**:
- `frontend/src/pages/Dashboard.tsx` — add parallel API calls:
  ```typescript
  const [incidents, rtas, complaints, audits, risks] = await Promise.all([
    incidentsApi.list(), rtasApi.list(), complaintsApi.list(),
    auditsApi.list(), risksApi.list()
  ]);
  ```
- Wire StatCard values to real counts
- Wire notification badge to `useNotificationStore.unreadCount`
- Wire recent activity to audit trail API
- Add error handling per card (independent failures)

**Definition of Done**: All 8 StatCards show real counts; activity feed populated; notification badge dynamic.
**Effort**: M | **Value**: H | **Expected lift**: D01 7.2 → 7.8, D02 5.4 → 6.4, D28 5.4 → 5.8

---

### 6. Guard `/metrics/resources` endpoint + consolidate health routes (D06, D32 → +0.3 WCS)

**Gap**: `src/api/routes/health.py` exposes `/metrics/resources` (memory, CPU, disk, threads, open files) without auth. Infrastructure fingerprinting risk. Additionally, health routes exist in both `main.py` and `health.py` — potential confusion.

**What to change**:
- `src/api/routes/health.py` — add `current_user: CurrentUser` to the `get_resource_metrics` endpoint. Keep `/healthz` and `/readyz` unauthenticated (required for probes).
- `src/api/routes/testing.py` — remove `environment` field from `/health` response.

**Definition of Done**: `/metrics/resources` returns 401 without auth; testing health doesn't leak env name.
**Effort**: S | **Value**: H | **Expected lift**: D06 8.0 → 8.1, D32 6.3 → 6.5

---

### 7. Complete runbook contacts and on-call rotation (D23, D05 → +0.5 WCS)

**Gap**: `incident-response.md` contact table has "TBD" entries. `escalation.md` on-call rotation says "TBD: PagerDuty / OpsGenie". Several runbooks are thin on step-by-step detail.

**What to change**:
- `docs/runbooks/incident-response.md` — fill in contact names, emails, phone numbers for each role
- `docs/runbooks/escalation.md` — define on-call rotation, tool (PagerDuty/OpsGenie), schedule
- Review all 25 runbooks — ensure each has: Trigger, Steps, Verification, Rollback, Contacts

**Definition of Done**: Zero "TBD" entries in any runbook; all 25 have minimum 5 sections.
**Effort**: S | **Value**: H | **Expected lift**: D23 5.4 → 6.0, D05 8.0 → 8.2

---

## Tier 2: Critical Workflow Improvements

### 8. Create 5 accessibility test files with axe-core (D03 → +1.0 WCS)

**Gap**: `jest-axe` installed, `axe-helper.ts` exists, `test:a11y` script configured — but zero `.a11y.test.tsx` files exist. All the infrastructure is there with no tests using it.

**What to change**:
- Create 5 files in `frontend/src/pages/__tests__/`:
  - `Dashboard.a11y.test.tsx`
  - `Login.a11y.test.tsx`
  - `Incidents.a11y.test.tsx`
  - `Complaints.a11y.test.tsx`
  - `AuditTemplateLibrary.a11y.test.tsx`
- Each file: render component, run `expect(await axe(container)).toHaveNoViolations()`

**Definition of Done**: `npm run test:a11y` runs 5 tests and exits 0.
**Effort**: M | **Value**: H | **Expected lift**: D03 4.5 → 5.5

---

### 9. Add Label, Alert, and Breadcrumb components (D02, D03 → +0.8 WCS)

**Gap**: Component inventory identifies Label (WCAG requirement), Alert (inline feedback), and Breadcrumb (navigation context) as high/medium priority missing components. No shared `<label>` component breaks form accessibility.

**What to change**:
- Create `frontend/src/components/ui/Label.tsx` — Radix `@radix-ui/react-label` wrapper with `htmlFor`, error state, required indicator
- Create `frontend/src/components/ui/Alert.tsx` — variants: info, success, warning, destructive; icon, title, description
- Create `frontend/src/components/ui/Breadcrumb.tsx` — auto-generate from React Router location; `Section > Module > Record`
- Add `<Breadcrumb />` to `Layout.tsx` below the top bar
- Use `<Label>` in all form inputs across pages

**Definition of Done**: 3 new components exist with unit tests; Breadcrumb shows on all pages; Labels on all form fields.
**Effort**: M | **Value**: H | **Expected lift**: D02 5.4 → 6.2, D03 4.5 → 5.0

---

### 10. Improve empty states across all list pages (D02, D01 → +0.5 WCS)

**Gap**: Empty states are plain text ("No incidents found", "No recent activity"). No illustrations, no CTAs, no guidance. Dashboard upcoming events is an empty `[]` that renders nothing.

**What to change**:
- Create `frontend/src/components/ui/EmptyState.tsx` — icon, title, description, primary action button
- Replace all plain-text empty states in: `Dashboard.tsx`, `Incidents.tsx`, `Complaints.tsx`, `RTAs.tsx`, `Risks.tsx`, `Audits.tsx`, `Actions.tsx`, `Policies.tsx`
- Each empty state should have: relevant Lucide icon, descriptive text, "Create new [entity]" CTA button

**Definition of Done**: All 8 key list pages show rich empty states with icon + CTA.
**Effort**: M | **Value**: H | **Expected lift**: D02 5.4 → 5.8, D01 7.2 → 7.5

---

### 11. Create Playwright E2E config + 3 critical-path specs (D15, D02 → +0.8 WCS)

**Gap**: `@playwright/test` is installed but no config, no specs, no CI job. Frontend user journeys are completely untested end-to-end.

**What to change**:
- Create `frontend/playwright.config.ts` — baseURL, webServer config, 3 projects (chromium, firefox, webkit)
- Create `frontend/tests/e2e/login.spec.ts` — login, verify dashboard, logout
- Create `frontend/tests/e2e/incident-lifecycle.spec.ts` — create incident, verify in list, view detail, update status
- Create `frontend/tests/e2e/audit-execution.spec.ts` — start audit run, answer questions, complete, view findings
- Add CI job (advisory initially): `npx playwright test --project=chromium`

**Definition of Done**: 3 specs pass against local dev; CI job configured.
**Effort**: M | **Value**: H | **Expected lift**: D15 5.4 → 6.2, D02 5.4 → 5.8

---

### 12. Raise test coverage threshold 35% → 50% with targeted tests (D15 → +0.8 WCS)

**Gap**: Coverage at 35% — below industry standard (70-80%). Both `pyproject.toml` and `ci.yml` aligned at 35%. 1,568 test functions exist but many test imports not behavior.

**What to change**:
- Write behavioral tests for the highest-value untested code:
  - `tests/unit/test_reference_number.py` — test `ReferenceNumberService.generate()` (race condition, prefix mapping, sequence)
  - `tests/unit/test_auth_routes.py` — test login, token refresh, password reset flows
  - `tests/unit/test_incident_routes.py` — test tenant isolation, CRUD, validation
  - `tests/unit/test_pagination.py` — test `paginate()` with edge cases
  - `tests/unit/test_idempotency.py` — test dedup, hash mismatch, cache expiry
- Raise threshold: `pyproject.toml` `fail_under = 50`; `ci.yml` `--cov-fail-under=50`

**Definition of Done**: CI passes at 50% coverage; 5+ new test files with behavioral tests.
**Effort**: L | **Value**: H | **Expected lift**: D15 5.4 → 6.2

---

## Tier 3: UI and UX Focus

### 13. Add DataTable + Pagination component (D02, D10 → +0.8 WCS)

**Gap**: Every list page has its own ad-hoc table implementation. No shared sortable, filterable, paginated table. Component inventory identifies DataTable as high priority.

**What to change**:
- Create `frontend/src/components/ui/DataTable.tsx` — props: columns, data, loading, emptyState, onSort, onFilter, onPageChange
- Create `frontend/src/components/ui/Pagination.tsx` — page numbers, prev/next, page size selector
- Refactor `Incidents.tsx` to use `<DataTable>` as proof-of-concept
- Progressive adoption: refactor remaining list pages (RTAs, Complaints, Risks, Audits, Users, Actions, Policies)

**Definition of Done**: DataTable + Pagination components exist; Incidents page uses DataTable; 2+ other pages migrated.
**Effort**: M | **Value**: H | **Expected lift**: D02 5.4 → 6.4, D10 8.0 → 8.3

---

### 14. Align design tokens with Tailwind + fix font mismatch (D02 → +0.4 WCS)

**Gap**: `design-tokens.css` uses `Inter` font and hex colors. `tailwind.config.js` uses `Plus Jakarta Sans` and HSL colors. Tokens exist but aren't wired into Tailwind. Two competing systems.

**What to change**:
- `frontend/src/styles/design-tokens.css` — change `--font-sans` from `Inter` to `Plus Jakarta Sans` to match Tailwind
- Add focus-ring tokens: `--ring-width`, `--ring-color`, `--ring-offset`
- Wire key tokens into `tailwind.config.js` via `theme.extend` referencing CSS custom properties
- Add `--input-border`, `--input-focus-border`, `--input-bg` tokens for form consistency
- Document the design token system in `docs/ux/design-tokens.md`

**Definition of Done**: Font consistent across tokens and Tailwind; tokens document covers usage; no competing color systems.
**Effort**: S | **Value**: M | **Expected lift**: D02 5.4 → 5.8

---

### 15. Restructure sidebar navigation per IA recommendations (D01, D02 → +0.6 WCS)

**Gap**: Sidebar has 8 sections with 30+ items, duplicate icons, duplicate routes (`/workforce/calendar` vs `/calendar`), and no collapsible sections. IA audit recommends consolidating to 7 groups with clearer hierarchy.

**What to change**:
- `frontend/src/components/Layout.tsx` — restructure nav sections:
  1. **Dashboard** (single item)
  2. **Incidents & Safety** (incidents, RTAs, near misses, complaints, investigations, CAPA)
  3. **Audits & Inspections** (audits, templates, trail, competence)
  4. **Risk & Compliance** (risks, risk register, compliance, ISO 27001, standards, policies)
  5. **Workforce** (engineers, assessments, inductions, training, calendar)
  6. **Documents & Evidence** (documents, document control, evidence, signatures)
  7. **Analytics & Reports** (analytics, dashboards, reports, exports, AI intelligence)
  8. **Admin** (users, workflows, settings, notifications, feature flags)
- Add collapsible sections (click section header to expand/collapse)
- Remove duplicate routes
- Use unique icons per section

**Definition of Done**: 8 logical nav groups; collapsible; no duplicate routes; no duplicate icons.
**Effort**: M | **Value**: H | **Expected lift**: D01 7.2 → 7.8, D02 5.4 → 6.0

---

## Impact Summary

| # | Focus Area | Dimensions | Effort | Category | Estimated Total WCS Lift |
|---|-----------|------------|--------|----------|--------------------------|
| 1 | Auth on 3 remaining modules | D06 | S | Low Effort / High Value | +0.5 |
| 2 | CSP header | D06 | S | Low Effort / High Value | +0.3 |
| 3 | Toast notification system | D02, D14 | S | Low Effort / High Value | +0.8 |
| 4 | Skeleton loading component | D02, D04 | S | Low Effort / High Value | +0.6 |
| 5 | Wire Dashboard to real APIs | D01, D02, D28 | M | Low Effort / High Value | +1.2 |
| 6 | Guard /metrics/resources | D06, D32 | S | Low Effort / High Value | +0.3 |
| 7 | Complete runbook contacts | D23, D05 | S | Low Effort / High Value | +0.5 |
| 8 | 5 accessibility tests | D03 | M | Critical Workflows | +1.0 |
| 9 | Label + Alert + Breadcrumb | D02, D03 | M | Critical Workflows | +0.8 |
| 10 | Rich empty states | D02, D01 | M | Critical Workflows | +0.5 |
| 11 | Playwright E2E (3 specs) | D15, D02 | M | Critical Workflows | +0.8 |
| 12 | Coverage 35% → 50% | D15 | L | Critical Workflows | +0.8 |
| 13 | DataTable + Pagination | D02, D10 | M | UI and UX | +0.8 |
| 14 | Design token alignment | D02 | S | UI and UX | +0.4 |
| 15 | Sidebar restructure | D01, D02 | M | UI and UX | +0.6 |
| | | | | **Total estimated lift** | **+9.9** |

### Projected WCS After Completion

If all 15 items are executed, the projected average WCS moves from **7.1 → ~8.1**, with the following dimension-level improvements:

| Dimension | Current WCS | Projected WCS | Change |
|-----------|------------|---------------|--------|
| D01 Product clarity | 7.2 | 8.1 | +0.9 |
| D02 UX quality | 5.4 | 7.2 | +1.8 |
| D03 Accessibility | 4.5 | 6.5 | +2.0 |
| D04 Performance | 5.4 | 5.7 | +0.3 |
| D05 Reliability | 8.0 | 8.2 | +0.2 |
| D06 Security | 8.0 | 9.1 | +1.1 |
| D10 API design | 8.0 | 8.3 | +0.3 |
| D14 Error handling | 8.0 | 8.3 | +0.3 |
| D15 Testing | 5.4 | 7.0 | +1.6 |
| D23 Runbooks | 5.4 | 6.0 | +0.6 |
| D28 Analytics | 5.4 | 5.8 | +0.4 |
| D32 Supportability | 6.3 | 6.5 | +0.2 |

---

## Execution Order (Recommended)

**Week 1 — Low Effort / High Value (items 1-4, 6-7)**:
1. Auth on planet_mark, uvdb, slo (item 1)
2. CSP header (item 2)
3. Guard /metrics/resources (item 6)
4. Toast system (item 3)
5. Skeleton component (item 4)
6. Runbook contacts (item 7)

**Week 2 — Critical Workflows + UX foundation (items 5, 8-10, 14)**:
7. Wire Dashboard APIs (item 5)
8. A11y test files (item 8)
9. Label + Alert + Breadcrumb (item 9)
10. Design token alignment (item 14)
11. Empty states (item 10)

**Week 3 — Testing + UI maturity (items 11-13, 15)**:
12. Playwright E2E setup (item 11)
13. DataTable + Pagination (item 13)
14. Sidebar restructure (item 15)
15. Coverage raise to 50% (item 12)
