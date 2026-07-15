# Change Ledger (CL-UAT-REMEDIATION-F500)

## File allowlist (exclusive)

- `frontend/src/utils/auth.ts`
- `frontend/src/utils/auth.test.ts`
- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/contexts/PortalAuthContext.tsx`
- `src/api/__init__.py`
- `src/api/routes/ocr_ops.py`
- `src/api/routes/health.py`
- `src/infrastructure/upstream/ai_status.py`
- `src/infrastructure/tasks/dlq_status.py`
- `src/main.py`
- `src/domain/models/__init__.py`
- `alembic/env.py`
- `alembic/versions/20260718_failed_tasks.py`
- `docs/ops/ocr-provider-readiness.md`
- `tests/fixtures/ocr/capabilities.json`
- `tests/unit/test_ocr_ops_meta.py`
- `tests/unit/test_ocr_artifacts.py`
- `tests/unit/test_dlq_status.py`
- `tests/integration/test_health.py`
- `scripts/governance/pr_body_uat_remediation_f500.md`

**Zero overlap** with partner tokens product surface, E4 Azure DI enablement, or SWA workflow YAML.

## 1) Summary

- **Feature / Change name:** fix(uat) — admin↔portal session handoff, canonical OCR meta, DLQ readiness honesty
- **User goal:** Production UAT residuals closed end-to-end (auth UX, API contract, DB schema, /readyz honesty) without Sev-1 process break
- **In scope:** Shared platform JWT stores; portal bootstrap from admin session; mount `/api/v1/meta/ocr-*`; create `failed_tasks` + honest DLQ probe statuses
- **Out of scope:** Enabling Azure DI dual-OCR in prod (E4 / DPO); incomplete silent-SSO redesign; SWA bake pipeline changes
- **Root cause (research):** (1) Dual auth stores with no handoff — admin `localStorage.access_token` vs portal `sessionStorage.platform_access_token`; logout/refresh asymmetry; `/portal` wrongly treated as login path. (2) OCR meta advertised `canonical_endpoint` `/api/v1/meta/ocr-providers` but only mounted under `/health/meta` → 404. (3) `FailedTask` ORM existed with no CREATE migration → `/readyz` DLQ `status=error`/`depth=null` false alarm.

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Admin → Portal UX | Staff login did not unlock portal shell | Shared JWT mirrored; portal bootstraps via `/auth/me` |
| Logout / 401 | One store cleared / `/portal` treated as login | `clearAuthState` + precise login-path check |
| OCR meta | Canonical path 404 | `/api/v1/meta/ocr-*` live; health path legacy alias |
| DB | `failed_tasks` missing | Alembic `20260718_failed_tasks` (≤32 chars) |
| `/readyz` DLQ | Blanket `error` + null depth | `ok` / `unavailable` / `error` + `error_class` |

## 3) Compatibility & Data Safety

- Auth: same platform JWT; no new cookie/SSO protocol — additive mirroring
- OCR: dual-mount alias; legacy health paths remain
- Migration: idempotent `has_table` guard; FK to `tenants`; unique `task_id`
- DLQ probe remains informational (does not flip 503)
- Rollback: revert merge; migration downgrade drops table if created by this revision

## 4) Acceptance Criteria

- [x] AC-01: `establishPlatformSession` / `clearAuthState` unit-tested; App + PortalAuth + client refresh use them
- [x] AC-02: PortalAuth bootstraps from shared JWT when `portal_user` absent
- [x] AC-03: `isLoginPagePath` only `/login` and `/portal/login` (not `/portal`)
- [x] AC-04: `GET /api/v1/meta/ocr-providers` and `/ocr-capabilities` return 200 (health alias retained)
- [x] AC-05: Alembic revision `20260718_failed_tasks` ≤32 chars; `down_revision=20260717_partner_api_tokens`
- [x] AC-06: Missing-table DLQ probe → `unavailable` (not bare `error`); generic failure → `error` + `error_class`
- [ ] AC-07: tip==LIVE after squash-merge; prod `/readyz` DLQ honest; purple-water portal opens after admin login without manual session bridge

## 5) Testing Evidence

- Unit: `auth.test.ts`, `test_ocr_ops_meta.py`, `test_ocr_artifacts.py`, `test_dlq_status.py`
- Integration: `test_health.py` DLQ status contract
- [ ] Post-merge prod smoke: admin login → `/portal` authenticated; `GET /api/v1/meta/ocr-providers` 200; `/readyz` `dlq.status` ∈ {ok,unavailable,error}

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Admin Entra login → navigate portal → work/track without second prompt (shared session)
- [x] CUJ-02: Ops hits canonical OCR meta (not 404)
- [x] CUJ-03: Readiness consumers see honest DLQ depth / unavailable note

## 7) Observability

- `/readyz` + `/api/v1/health/readyz` `dlq.error_class` / `note` for schema gaps
- OCR `meta_endpoint` on readyz points at canonical path

## 8) Release Plan

- Squash-merge tip==LIVE → API migrate `failed_tasks` → SWA bake → verify portal handoff + OCR meta + DLQ on prod

## 9) Rollback Plan

- **Rollback steps:** Revert squash/merge on `main`; if migration applied, run downgrade for `20260718_failed_tasks` only when safe
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- This Change Ledger
- Fortune-500 UAT residuals (auth split, OCR 404, DLQ false alarm)
- Related tip: `fe299f77` (#1020)

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — touched surfaces only
- [x] **Gate 2:** Unit + integration — OCR/DLQ/auth tests
- [x] **Gate 3:** Frontend — auth helpers + portal bootstrap
- [ ] **Gate 4:** tip==LIVE prod verification
