# Change Ledger (CL-DS-4-5)

**Path claim:** `path11/ds-versions-fk`

## File allowlist (exclusive)

- `src/domain/services/document_version_service.py`
- `src/domain/services/gkb_control_library_link.py`
- `src/domain/models/document_control.py`
- `src/api/routes/documents.py`
- `src/api/routes/document_control.py`
- `alembic/versions/20260724_ds_library_control_fk.py`
- `frontend/src/pages/DocumentDetail.tsx`
- `frontend/src/pages/DocumentControl.tsx`
- `frontend/src/components/DocumentVersionControlBar.tsx`
- `frontend/src/api/documentControlClient.ts`
- `frontend/src/i18n/locales/en.json`
- `tests/unit/test_ds_versions_fk.py`
- `tests/unit/test_gkb_golden_thread_read_path.py`
- `tests/unit/test_document_version_service.py`
- `scripts/governance/pr_body_ds_versions_fk.md`

**Out of scope:** DS-0 preview/Q&A, DS-1b Azure DI, DS-6 consumer cutover, dependabot.

## 1) Summary

- **Feature / Change name:** DS-4 + DS-5 — file-bearing library versions + hard Library↔Control FK
- **User goal:** Revise library documents with a replacement file and re-index; edit draft titles without version bumps; migrate safe soft matches to a hard controlled→library FK; honest golden-thread UI copy.
- **In scope:** Multipart revise + reindex, filename `_vX.Y` advisory hint, PATCH title on draft, Alembic FK + backfill, golden-thread read path uses hard link when present
- **Out of scope:** Publish-event emission, Azure DI, Planet Mark cutover, steward reconciliation UI
- **Feature flag / kill switch:** None — additive schema column + honest read paths

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Library revise | Metadata-only JSON POST | Multipart revise accepts optional file + queues reindex |
| Title edit | No draft metadata PATCH | PATCH title/description without version bump |
| Filename `_v2.1` | Ignored | Advisory `filename_version_hint` on version rows / upload |
| Control↔Library | Soft title/reference candidate only | Nullable `library_document_id` FK + unambiguous backfill |
| Golden thread UI | “Candidate” oversell | Hard link vs unverified candidate labelled separately |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive column + API fields; revise endpoint now multipart (frontend updated)
- **Breaking changes:** Clients posting JSON to `POST /documents/{id}/versions` must switch to multipart Form
- **Migration:** Backfills FK only when exactly one same-tenant title/reference match exists
- **Rollback strategy:** Revert deploy; column nullable — soft-match path still works

## 4) Acceptance Criteria (AC)

- [x] AC-01: Revise accepts file upload, stores blob, updates draft version row, queues reindex
- [x] AC-02: Filename `_v2.1` parsed as advisory hint only (no auto bump)
- [x] AC-03: PATCH title on draft/working rows without version bump
- [x] AC-04: Publish still supersedes prior published tip (existing pattern)
- [x] AC-05: `controlled_documents.library_document_id` FK + safe backfill migration
- [x] AC-06: Golden-thread read path reports `linked` when hard FK present; candidate when not
- [x] AC-07: UI copy no longer implies hard link without FK

## 5) Testing Evidence

- [x] `pytest tests/unit/test_ds_versions_fk.py tests/unit/test_document_version_service.py tests/unit/test_gkb_golden_thread_read_path.py`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Revise with replacement PDF queues reindex job
- [x] CUJ-02: Title PATCH on draft does not change version tip
- [x] CUJ-03: Hard-linked control doc shows linked library + evidence; soft match still unverified

## 7) Observability & Ops

- Reindex via existing `index_jobs` + Celery dispatch on file-bearing revise
- Migration logs unlinked rows implicitly (no FK set = remains soft-only)

## 8) Release Plan

1. Merge after CI green
2. Run Alembic upgrade on staging
3. Spot-check DocumentDetail Versions tab revise-with-file + Document Control golden thread

## 9) Rollback Plan

1. Revert squash commit
2. `alembic downgrade` drops FK column (orphans revert to soft match)

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: Contracts (multipart revise, PATCH metadata, FK migration)
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [x] Gate 4: Canary (N/A ok)
- [ ] Gate 5: Production verification plan
