# Top 20 World-Class Enhancement Action Plan

**Generated:** 2026-03-07 | **Methodology:** 3-wave deep-dive (backend/API/security → frontend/UX/workflows → CI/testing/governance)

**Selection criteria:** Low effort → high impact · UI/UX polish · Critical workflow integrity · Biggest WCS movers

---

## Tier 1 — Quick Wins (Effort: S | Batch 1)

| # | Item | Wave | WCS Dimensions | Evidence |
|---|------|------|----------------|----------|
| 1 | **Portal tenant_id: all portal records created with NULL tenant_id** | W1 | Data Integrity, Multi-tenancy, Security | `employee_portal.py` lines 202-337 — Incident/Complaint/RTA/NearMiss created without `tenant_id`, orphaning portal data |
| 2 | **Rate limiter bug: authenticated multiplier never fires** | W1 | Security, Reliability | `rate_limiter.py:253` checks `"user:"` prefix but `get_client_identifier()` returns `"token:"` — 2× multiplier is dead code |
| 3 | **Auth route errors: 10 plain-string HTTPExceptions, zero ErrorCode usage** | W1 | API Consistency, DX | `auth.py` — 10 `detail=` strings; no `ErrorCode` or `api_error()` import |
| 4 | **Skeleton loaders: 12 pages still use Loader2 spinner** | W2 | Perceived Performance, Visual Polish | Policies, Actions, RTAs, ComplaintDetail, IncidentDetail, MobileAudit, Engineers, Assessments, Calendar, Training, UserManagement, AuditTemplateLibrary |
| 5 | **Secret scanning: no Gitleaks CI job** | W3 | Security, ISO 27001 | CI has zero `gitleaks` references; no `.gitleaks.toml` |
| 6 | **OpenCensus ghost deps: 3 unused packages in requirements.txt** | W1 | Supply Chain, Build Hygiene | `requirements.txt:49-52` lists opencensus; `azure_monitor.py` imports only opentelemetry |
| 7 | **ADR numbering: all 4 ADR numbers are duplicated** | W3 | Governance, Auditability | `docs/adr/` has 8 files for 4 unique numbers (0001-0004 each appear twice) |

**Expected impact:** Fixes 2 critical data bugs, 1 security blind spot, and modernises loading UX across the entire app.

---

## Tier 2 — Important Movers (Effort: S–M | Batch 2)

| # | Item | Wave | WCS Dimensions | Evidence |
|---|------|------|----------------|----------|
| 8 | **OpenAPI baseline: contract stability check disabled** | W3 | API Stability, Governance | CI `openapi-contract-check` job prints "No baseline found" and continues — effectively no-op |
| 9 | **Native confirm() → Dialog: 3 browser confirm() calls** | W2 | Brand Consistency, Accessibility | `FormsList.tsx:92`, `ContractsManagement.tsx:130`, `InvestigationDetail.tsx:282` |
| 10 | **Keyboard a11y: table rows missing role/tabIndex in Audits + RTAs** | W2 | Accessibility (WCAG 2.1 AA) | `Audits.tsx` and `RTAs.tsx` — clickable rows without keyboard support; detail pages lack Escape handler |
| 11 | **Search debounce: 4 pages filter on every keystroke** | W2 | Performance, Responsiveness | Incidents, Complaints, Actions, Policies — synchronous `.filter()` on each keystroke |
| 12 | **Empty states: 7 pages use ad-hoc inline text** | W2 | Visual Consistency, User Guidance | Audits, Policies, Actions, Documents, RTAs, Investigations, Standards — no `EmptyState` component |
| 13 | **Complaint dup detection: raw dict leaks internal ID** | W1 | API Consistency, Security | `complaints.py:81-89` returns `existing_id` in a raw dict instead of `api_error()` |
| 14 | **Input sanitization: nh3.clean() used in 1 of ~40 routes** | W1 | XSS Prevention, Data Integrity | Only `capa.py` uses `sanitize_field()`; all other schemas accept raw HTML |

**Expected impact:** Closes remaining API consistency gaps, hardens accessibility, and polishes the search/empty/confirm UX patterns.

---

## Tier 3 — High-Value Stretch (Effort: M | Batch 3)

| # | Item | Wave | WCS Dimensions | Evidence |
|---|------|------|----------------|----------|
| 15 | **Form validation UX: no asterisks, no inline field errors** | W2 | Form UX, Error Recovery, Accessibility | Incidents, Complaints, Risks create forms — HTML `required` only, no visual indicators |
| 16 | **Page transitions: framer-motion installed but unused** | W2 | Visual Polish, Smoothness | `package.json` has `framer-motion ^12.34.5`; zero `AnimatePresence` or `motion.div` in `App.tsx` |
| 17 | **A11y test files: zero exist, CI passes silently** | W3 | Accessibility Compliance | `test:a11y` runs with `--passWithNoTests`; `axe-helper.ts` is dead code |
| 18 | **Service layer bypass: 10 route endpoints skip services** | W1 | Architecture, Testability, Cache | `incidents.py` and `complaints.py` use direct SQLAlchemy; miss cache invalidation + telemetry |
| 19 | **Coverage target: fail_under = 35%** | W3 | Testing Maturity, Reliability | `pyproject.toml:217` and `ci.yml:234` both set 35% — well below enterprise norm of 60%+ |
| 20 | **Optimistic updates: 4 list pages full-refetch after create** | W2 | Perceived Performance | Incidents, Complaints, Policies, Actions call `load*()` after every create |

**Expected impact:** Elevates architecture, testing maturity, and UX smoothness to enterprise-grade standards.

---

## Validation Checklist

After each tier, verify:

- [ ] All modified files pass `black` + `isort` + `flake8`
- [ ] `mypy` passes with no new errors
- [ ] `pytest` passes with coverage ≥ current `fail_under`
- [ ] Frontend `npm run lint` + `npm run build` clean
- [ ] CI pipeline green on staging
- [ ] Deployment to staging + production verified
