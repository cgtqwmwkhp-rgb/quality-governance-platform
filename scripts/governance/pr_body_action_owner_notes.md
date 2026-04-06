# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Action owner commentary and per-action evidence uploads
- **User goal (1-2 lines):** Let action owners add time-stamped notes on the unified action detail page and attach evidence files scoped to that action, with tenant-safe APIs and storage.
- **In scope:** New `action_owner_notes` table; GET/POST `/api/v1/actions/by-key/notes`; evidence upload/list for `source_module=action` with `action_key`; Action detail UI (notes timeline, uploads, downloads, delete).
- **Out of scope:** Editing or deleting historical notes; cross-tenant reporting; new RBAC roles beyond existing authenticated tenant scope.
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/ActionDetail.tsx`, `frontend/src/api/client.ts`
- **Backend (handlers/services):** `src/api/routes/actions.py`, `src/api/routes/evidence_assets.py`
- **APIs (endpoints changed/added):** Added GET/POST `/api/v1/actions/by-key/notes`; extended POST `/api/v1/evidence-assets/upload` (optional `action_key` when `source_module=action`); extended GET `/api/v1/evidence-assets/` with `action_key` filter (Annotated query param for safe defaults).
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** New TS types `ActionOwnerNote`, `ActionOwnerNoteListResponse`; `evidenceAssetsApi` optional `action_key` / `source_id`.
- **Database (migrations/entities/indexes):** Alembic `e4f5a6b7c8d9` — `action_owner_notes` (tenant_id, action_key, author_id, body, timestamps, indexes).
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive — existing evidence uploads unchanged when `source_module` is not `action`.
- **Tolerant reader / strict writer applied?** Yes — list filter uses explicit `action_key` or numeric `source_id` branch.
- **Breaking changes:** None for existing clients; `source_id` on upload is optional only when `source_module=action` (otherwise still required).
- **Migration plan:** Run Alembic upgrade before serving new note endpoints.
- **Rollback strategy (DB):** Downgrade migration drops `action_owner_notes`; action-linked evidence rows remain (optional manual cleanup).

## 4) Acceptance Criteria (AC)
- [x] AC-01: Owner can list and append notes; each row has server `created_at` and author resolution.
- [x] AC-02: Evidence upload with `source_module=action` requires resolvable `action_key` in tenant; blob path uses colon-safe segment.
- [x] AC-03: Evidence list supports `action_key` to return only that action’s attachments.
- [x] AC-04: Action detail UI shows commentary (newest first) and attachment list with upload/download/delete.
- [x] AC-05: `make pr-ready` passes (lint, mypy, unit/integration suites in script).

## 5) Testing Evidence (link to runs)
- [x] Lint — via `make pr-ready`
- [x] Typecheck — mypy via `make pr-ready`
- [x] Build — frontend checks in `make pr-ready`
- [x] Unit tests — via `make pr-ready`
- [x] Integration tests — via `make pr-ready`
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open action by key → add owner note → see timestamped entry in list.
- [x] CUJ-02: Open action by key → upload evidence → list filters by `action_key` → download via signed URL.

## 7) Observability & Ops
- **Logs:** Existing evidence upload logging uses normalized source ref.
- **Metrics:** Existing `documents.uploaded` on successful evidence upload.
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Apply migration; smoke action detail, note POST/GET, evidence upload/list.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health, readiness, version SHA; spot-check action detail.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Errors on new endpoints or migration failure.
- **Rollback steps:** Revert deploy; run Alembic downgrade if migration applied; prior app versions ignore new table.
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: After merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
