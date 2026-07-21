# Change Ledger (CL-GOV-LIB-W0-TAXONOMY-PEL)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W0 — taxonomy + `pel_doc_ref` foundation
- **User goal (1–2 lines):** Give the existing Document library a controlled 2-level category taxonomy (13 sections / 73 subcategories) and an atomically-allocated `PEL-<SECTION>-<SUB>-<SEQ>` reference that sits alongside the existing `DOC-YYYY-####` reference, plus optional site/workshop binding via the existing `Location` model — with zero disruption to current upload/list flows.
- **In scope:** `document_categories` + `document_tags` + `pel_doc_ref_counters` tables (Alembic migration + idempotent seed from `specs/governance-library/taxonomy.json`); `documents.category_id` / `documents.pel_doc_ref` / `documents.site_location_id` nullable columns; `allocate_pel_doc_ref()` service (atomic `UPDATE…RETURNING`); `GET /api/v1/document-categories` (tree) + `GET .../tags` (any active user) + `POST .../reseed` (admin-only, idempotent); upload/list endpoints wired to accept/filter `category_id` and `site_location_id`; category filter dropdown on the Documents page; unit tests for seed idempotency + PEL allocation concurrency/uniqueness
- **Out of scope:** Review packs, AI horizon, disposal/retention automation (explicitly deferred by decision log); Site CRUD UI (Location admin API already exists under `/api/v1/assets/locations`); tag-picker UI (tags API is read-only for now)
- **Feature flag / kill switch:** None required — every new field is nullable/optional and additive; `category_id`/`site_location_id` are opt-in on upload (omit both and behavior is byte-for-byte the pre-existing upload path)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/Documents.tsx` — new "Category" filter `<Select>` (grouped by section, sourced from `GET /api/v1/document-categories`), synced to the shareable URL (`?category=<id>`), passed through to the list API as `category_id`
- **Backend (handlers/services):**
  - `src/domain/services/document_category_service.py` — `seed_document_categories()` (idempotent upsert by natural key `taxonomy_id` / `slug`), `allocate_pel_doc_ref()` (atomic per-category sequence allocation)
  - `src/domain/services/document_category_seed_data.py` — loads `specs/governance-library/taxonomy.json`, forces `06.04` (HGV/O-licence) inactive, defines the tag vocabulary (ISO standard tags dropped; `planet-mark` + subject tags kept)
  - `src/api/routes/documents.py` — `upload_document` allocates `pel_doc_ref` when `category_id` is supplied (only after file validation passes, so a rejected upload never burns a sequence number) and validates `site_location_id` against `Location`; `list_documents` gains `category_id` / `site_location_id` filters
  - `scripts/governance/library/seed_document_categories.py` — CLI to re-run the idempotent seed (e.g. after editing `taxonomy.json`)
- **APIs (endpoints changed/added):**
  - `GET /api/v1/document-categories` — 2-level tree (section → subcategories), `include_inactive` query flag, any active user
  - `GET /api/v1/document-categories/tags` — tag vocabulary, any active user
  - `POST /api/v1/document-categories/reseed` — idempotent taxonomy reseed, `admin:manage` only
  - `POST /api/v1/documents/upload` — new optional form fields `category_id`, `site_location_id`; response gains `pel_doc_ref`
  - `GET /api/v1/documents` — new optional query filters `category_id`, `site_location_id`; response items gain `category_id` / `pel_doc_ref` / `site_location_id`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `DocumentResponse` / `DocumentUploadResponse` extended with the three new optional fields (tolerant reader — old clients ignore them)
- **Database (migrations/entities/indexes):** `20260719_gov_lib_w0_taxonomy_pel` —
  - `document_categories` (taxonomy row incl. `taxonomy_id` unique, `parent_id` self-FK, `level`, `ref_prefix`, `active`) — seeded 86 rows on first apply (Postgres), `06.04` seeded `active=false`
  - `document_tags` (controlled vocabulary; seeded without `iso-9001/14001/45001/27001`, keeps `planet-mark` + subject tags)
  - `pel_doc_ref_counters` (`category_id` PK/FK → `document_categories.id`, `next_seq`) — one row per level-2 subcategory, backs atomic allocation
  - `documents.category_id` (nullable FK → `document_categories`, `SET NULL` on delete), `documents.pel_doc_ref` (nullable unique string), `documents.site_location_id` (nullable FK → `locations`, `SET NULL` on delete)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive — new nullable columns, new tables, new optional request/response fields. Existing `DOC-YYYY-####` `reference_number` is untouched; `pel_doc_ref` is a second, independent reference that is only populated when a caller opts in with `category_id`.
- **Tolerant reader / strict writer applied?** Yes — `_document_to_response()` uses `getattr(document, "field", None)` for all three new fields so legacy/mocked `Document` instances (as used by several pre-existing unit tests) never 500; `category_id`/`site_location_id` are normalized with `isinstance(x, int)` rather than `is not None` so the FastAPI `Form(None)` sentinel default can't leak through when the route coroutine is invoked directly (unit tests) vs. via the HTTP layer.
- **Breaking changes:** None. `ControlledDocument` (control layer) is untouched; `Document` (file SoT) gains only nullable/optional fields.
- **Migration plan:** Single Alembic revision, chained onto current head (`20260719_index_job_document_progress`). Table creation + column adds are safe on a live DB (no locks beyond standard `ADD COLUMN`/`CREATE TABLE`). Seed of the 86 taxonomy rows + tag vocabulary + counters runs inline in the migration's `upgrade()` (Postgres-only, guarded by "seed only if `document_categories` is empty") so first deploy is self-contained; `seed_document_categories()` is also exposed as an idempotent service/CLI for re-applying `taxonomy.json` after edits without a new migration.
- **Rollback strategy (DB):** `downgrade()` drops `documents.category_id` / `documents.pel_doc_ref` / `documents.site_location_id` and drops `pel_doc_ref_counters`, `document_tags`, `document_categories` in FK-safe order.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `document_categories` seeded with 86 rows (13 sections + 73 subcategories) from `specs/governance-library/taxonomy.json`; `06.04` (HGV/O-licence) seeded `active=false`; reseed re-asserts deactivation even if manually reactivated
- [x] AC-02: `document_tags` seeded without `iso-9001` / `iso-14001` / `iso-45001` / `iso-27001`; `planet-mark` and subject tags retained
- [x] AC-03: `documents.category_id` (nullable FK) + `documents.pel_doc_ref` (nullable unique) added alongside existing `reference_number` — no existing document rows affected
- [x] AC-04: `allocate_pel_doc_ref()` is atomic under concurrency (single `UPDATE … RETURNING`), rejects level-1/inactive categories and missing category/counter rows, and produces gapless, non-colliding sequences per category
- [x] AC-05: `GET /api/v1/document-categories` returns the section→subcategory tree; `POST /api/v1/document-categories/reseed` is admin-only and idempotent (repeated calls create nothing new)
- [x] AC-06: `documents.site_location_id` (nullable FK → `locations`) wired end-to-end: upload validates the location exists, list endpoint filters by it, response schema exposes it — no new Site table
- [x] AC-07: Documents page has a working category filter (grouped by section) that round-trips through the shareable URL
- [x] AC-08: No review packs / AI horizon / disposal logic introduced

## 5) Testing Evidence (link to runs)
- [x] Lint — no new linter errors on touched files (`ReadLints` clean)
- [x] Typecheck — `npx tsc --noEmit` clean on frontend
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_document_category_seed.py` (13 tests) + `tests/unit/test_pel_doc_ref_allocation.py` (9 tests) — 22/22 passing; full backend suite `pytest tests/unit/` — 2820/2822 passing (the only 2 remaining failures are `test_gemini_review_upstream_breaker.py`, confirmed pre-existing/unrelated by reproducing identically on `origin/main` with this branch's changes stashed)
- [x] Frontend unit tests — `Documents.test.tsx` + `Documents.a11y.test.tsx` — 10/10 passing after the category-filter change
- [ ] Integration tests — CI after open
- [ ] Contract tests (if applicable) — N/A (additive-only fields; no OpenAPI baseline break expected)
- [ ] E2E Smoke — CI after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Upload a document without `category_id`/`site_location_id` — behaves exactly as before (no `pel_doc_ref` allocated, response unchanged apart from new `null` fields)
- [x] CUJ-02: Upload a document with a valid level-2 `category_id` — `pel_doc_ref` allocated as `<ref_prefix>-<seq:03d>`, sequence never burned by a rejected/invalid file
- [x] CUJ-03: Upload with an unknown `site_location_id` — rejected with a clear 400 before any DB writes
- [x] CUJ-04: Two concurrent allocations against the same category never collide or skip (validated via true concurrent file-based SQLite connections in `test_pel_doc_ref_allocation.py`)
- [x] CUJ-05: Filtering the Documents page by category narrows the list via `category_id` and the filter survives a page reload (URL param)
- [x] CUJ-06: Re-running the seed (migration re-apply in dev, or `POST /reseed`) never duplicates categories/tags/counters and always re-forces `06.04` inactive

## 7) Observability & Ops
- **Logs:** `document_category_service` logs on reseed (categories created/updated counts) via the `/reseed` route handler
- **Metrics:** None new (upload already emits `documents.uploaded`)
- **Alerts:** None new
- **Runbook updates:** `docs/governance/tenant_id_catalog_exceptions.json` — added `document_categories` / `document_tags` as C-01 catalog exceptions (shared/global taxonomy + tag vocabulary, not tenant-owned entities, owner: Governance/Quality platform team)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Apply migration; confirm `document_categories` has 86 rows with `06.04` inactive; confirm `document_tags` has no `iso-*` rows; upload a document with a level-2 `category_id` and confirm `pel_doc_ref` is allocated; confirm Documents page category filter loads and filters
- **Canary plan:** N/A — fully additive/opt-in, safe for a normal rollout
- **Prod post-deploy checks:** `SELECT count(*) FROM document_categories` = 86; `SELECT active FROM document_categories WHERE taxonomy_id='06.04'` = `false`; spot-check `GET /api/v1/document-categories` returns the tree

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration failure on apply, or `pel_doc_ref` allocation contention/uniqueness issue observed in production
- **Rollback steps:** Revert PR; `alembic downgrade -1` (drops the three new tables and three new `documents` columns — no data loss on existing documents since all three fields are additive/nullable)
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (opened as PR; verification pending CI + staging deploy)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive-only; `ControlledDocument` control layer untouched)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — N/A, additive/opt-in rollout
- [x] **Gate 5:** Production verification plan + monitoring ready
