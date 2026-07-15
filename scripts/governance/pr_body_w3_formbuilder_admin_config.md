# Change Ledger (CL-W3-FORMBUILDER-ADMIN-CONFIG)

## 1) Summary
- **Feature / Change name:** W3-FORMBUILDER — wire admin FormBuilder/FormsList to `/api/v1/admin/config/templates`
- **User goal (1–2 lines):** Let admins list, create, edit, publish, duplicate, and delete form templates from the Form Builder UI using the existing backend CRUD spine instead of mock/local state.
- **In scope:** `formConfigClient.ts`; `FormBuilder.tsx` + `FormsList.tsx` API wiring; list/get eager-load of steps/fields; `is_published` on `FormTemplateUpdate`; unit + smoke tests; Change Ledger
- **Out of scope:** App.tsx / Layout.tsx routing; portal submission spine (dual-spine ADR deferred — portal forms remain second spine); audit-builder / OCR / investigation lanes; DynamicForm renderer changes
- **Feature flag / kill switch:** N/A — replaces mock data with existing admin config API

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `FormsList` loads/deletes/publishes/duplicates via API; `FormBuilder` loads/saves templates with step+field sync
- **Backend (handlers/services):** `form_config` routes — selectinload on list/get; unpublish clears `published_at`
- **APIs (endpoints changed/added):** None new — client calls existing `/api/v1/admin/config/templates` (+ steps/fields/publish)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `FormTemplateUpdate.is_published`; FE types in `formConfigClient.ts`
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive — backend accepts optional `is_published` on PATCH; FE replaces mock-only paths
- **Tolerant reader / strict writer applied?** Yes — list items derive `steps_count`/`fields_count` from nested steps when present
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only
- **Dual-spine note:** Admin config templates are spine 1; portal runtime forms remain spine 2 until dual-spine ADR lands (out of scope)

## 4) Acceptance Criteria (AC)
- [x] AC-01: `FormsList` lists templates from `GET /api/v1/admin/config/templates` (no `MOCK_FORMS`)
- [x] AC-02: `FormBuilder` creates via POST and loads/edits via GET + PATCH with step/field sync
- [x] AC-03: Publish/unpublish/delete/duplicate call existing backend endpoints
- [x] AC-04: Exclusive allowlist only; no App/Layout/investigation/audit-builder/OCR changes

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `formConfigClient.test.ts`, `FormsList.test.tsx`, `FormBuilder.test.tsx` (local)
- [x] Backend unit — `tests/unit/test_form_config_service.py` (local)
- [x] Smoke — `tests/test_smoke_form_config.py` incl. unpublish (local, auth-gated)
- [ ] E2E Smoke — N/A (admin UI wiring only)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin opens Forms list → sees API-backed templates with step/field counts
- [x] CUJ-02: Admin creates form → POST template with steps → navigates to edit URL
- [x] CUJ-03: Admin publishes draft → `POST .../publish`; unpublish → `PATCH is_published:false`

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/admin/forms`, create/edit/publish a template against staging API
- **Canary plan:** N/A
- **Prod post-deploy checks:** List loads; create/save round-trip

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Form Builder save/list failures blocking admin workflows
- **Rollback steps:** Revert PR; UI falls back to prior mock/empty state on main
- **Owner:** Platform / Path-11 admin config track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE client contracts aligned to existing form_config OpenAPI
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/admin/FormBuilder.tsx`
- `frontend/src/pages/admin/FormsList.tsx`
- `frontend/src/api/formConfigClient.ts` (NEW)
- `frontend/src/api/formConfigClient.test.ts` (NEW)
- `frontend/src/pages/admin/__tests__/FormsList.test.tsx` (NEW)
- `frontend/src/pages/admin/__tests__/FormBuilder.test.tsx` (NEW)
- `src/api/routes/form_config.py`
- `src/api/schemas/form_config.py`
- `src/domain/models/form_config.py` (no change expected)
- `src/domain/services/form_config_service.py` (no change expected)
- `tests/unit/test_form_config_service.py`
- `tests/test_smoke_form_config.py`
- `scripts/governance/pr_body_w3_formbuilder_admin_config.md`

**Forbidden:** App.tsx, Layout.tsx, investigation*, audit-builder, OCR, audits routes.
