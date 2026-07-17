# Change Ledger (CL-ADM-H1-TIMEOUTS)

## 1) Summary
- **Feature / Change name:** ADM-H1 — Admin pages harden against 503/timeouts
- **User goal (1–2 lines):** Stop Admin Console / Users / Audit Trail / Forms / Contracts from crashing into ErrorBoundary or spamming timeout toasts when admin config APIs are slow or return 503.
- **In scope:** Contracts API wiring + inline Retry; AdminDashboard soft stats; AuditTrail API shape fix; UserManagement/FormsList defensive loads; axios toast dedupe + `suppressErrorToast`; contracts list route JSON 503; composite index on contracts tenant filter
- **Out of scope:** RiskProfile, RiskHeatMap, risk_register import (#1093–#1095), App.tsx ErrorBoundary, redesign
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `ContractsManagement`, `AdminDashboard`, `AuditTrail`, `UserManagement`, `FormsList`, `adminLoadHelpers`, `client.ts`, `formConfigClient`, `auditTrailClient`, `usersClient`
- **Backend:** `form_config.py` list_contracts error envelope; `Contract` composite index
- **APIs:** `/api/v1/admin/config/contracts` returns JSON 503 on SQLAlchemy failure (not blank gateway 503 when app catches)
- **Tests:** `ContractsManagement.test.tsx`, `AdminDashboard.test.tsx`, `UserManagement.test.tsx`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE error states; backend list response shape unchanged on success
- **Tolerant reader / strict writer:** FE never maps failed loads to empty lists; stats show `—` / unavailable labels
- **Breaking changes:** None on success paths
- **Migration plan:** Index declared on model (existing DBs may add index on next migration cycle)
- **Rollback strategy:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Contracts page shows inline unavailable + Retry on 503/timeout; no toast spam
- [x] AC-02: AdminDashboard loads partial stats; banner on failed sources; never throws
- [x] AC-03: AuditTrail uses `response.data.items` (not `.map` on object); inline unavailable on failure
- [x] AC-04: UserManagement + FormsList catch expected HTTP errors with honesty banner + Retry
- [x] AC-05: axios interceptor dedupes error toasts + honors `suppressErrorToast`
- [x] AC-06: Backend `list_contracts` logs and returns JSON 503 detail on SQLAlchemyError
- [x] AC-07: Soft en/cy keys for new admin honesty strings only
- [x] AC-08: Vitest coverage for Contracts 503 honesty + AdminDashboard soft-fail

## 5) Testing Evidence (link to runs)
- [ ] CI — linked after push

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Admin → Contracts with API 503 → inline unavailable + Retry, page shell renders
- [x] **CUJ-02:** Admin Console with contracts API failure → partial stats + banner, quick actions still navigable

## 7) Observability & Ops
- **Logs:** `trackError` via `captureAdminLoadError` with `extra.surface=admin`
- **Toast:** deduped global errors; admin list loads suppress global toast

## 8) Release Plan
- **Staging:** Hit `/admin/contracts` with API degraded → confirm inline Retry, no toast stack

## 9) Rollback Plan
- **Rollback trigger:** Admin pages blank or mutations broken
- **Rollback steps:** Revert PR
- **Owner:** Platform / Admin track

## 10) Evidence Pack
- CI run(s): linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Implementation + local tests
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked

## Root cause (honesty)
1. **Toast spam:** Global axios interceptor emitted one toast per failed request with no dedupe; admin pages fire parallel loads.
2. **ErrorBoundary crashes:** Historical AuditTrail wired code called `.map` on `response.data` (paginated object) instead of `response.data.items`; UserManagement assumed `user.roles` always defined.
3. **Contracts 503:** Backend list route had no app-level catch — infra timeout/DB errors surfaced as blank 503; FE Contracts page was stubbed and did not handle API failure inline.

## Exclusive allowlist (this PR)
- `frontend/src/pages/admin/**`
- `frontend/src/pages/AuditTrail.tsx`
- `frontend/src/api/client.ts` (toast dedupe + suppressErrorToast + contractsApi silent config)
- `frontend/src/api/formConfigClient.ts`
- `frontend/src/api/auditTrailClient.ts`
- `frontend/src/api/usersClient.ts`
- `frontend/src/i18n/locales/en.json` (admin.* additions)
- `frontend/src/i18n/locales/cy.json` (admin.* additions)
- `src/api/routes/form_config.py`
- `src/domain/models/form_config.py`
- `scripts/governance/pr_body_admin_harden_timeouts.md`
