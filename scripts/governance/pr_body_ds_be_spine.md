# Change Ledger (CL-DS-BE-SPINE)

**Path claim:** `path11/ds-be-spine`

## File allowlist (exclusive)

- `src/domain/services/document_intelligence_service.py`
- `src/domain/services/index_job_service.py`
- `src/infrastructure/tasks/document_index_tasks.py`
- `src/infrastructure/tasks/celery_app.py`
- `src/infrastructure/upstream/ai_status.py`
- `src/api/routes/documents.py`
- `tests/unit/test_document_intelligence_service.py`
- `tests/unit/test_index_job_service.py`
- `tests/unit/test_document_index_tasks.py`
- `tests/unit/test_library_extraction_cer_gate.py`
- `tests/unit/test_ocr_ops_meta.py`
- `tests/fixtures/ocr/library_golden_corpus.json`
- `scripts/governance/pr_body_ds_be_spine.md`

**Out of scope:** `frontend/`, `DocumentDetail.tsx`, Planet Mark cutover (DS-6), Azure DI prod enablement (DS-1b), Document Control.

## 1) Summary

- **Feature / Change name:** DS-1/DS-2 — Document Intelligence Spine backend (Library Mistral OCR + Celery index jobs)
- **User goal:** Library uploads/reprocess use shared Mistral-backed extraction when native text is thin; indexing runs asynchronously via real `index_jobs` + Celery worker (OCR → chunk → Voyage → Pinecone).
- **In scope:** `DocumentIntelligenceService`, `IndexJobService`, Celery task registration, upload/reprocess wiring, OCR meta honesty, CER golden-corpus gate
- **Out of scope:** Frontend downstream UI, Azure DI prod enablement, Planet Mark OCR cutover
- **Feature flag / kill switch:** Sync fallback when Celery dispatch unavailable (dev/local)

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Library upload extract | Native-only inline | `DocumentIntelligenceService` with Mistral fallback on thin/empty native |
| Indexing | Inline sync in upload route | `index_jobs` row + Celery worker (sync fallback when broker unavailable) |
| Reprocess | Not available | `POST /documents/{id}/reprocess` queues reindex job |
| OCR meta | Audit import only | Adds `library_document_ocr` capability + `library_documents` readiness block |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive API fields (`index_job_id` on upload response); existing upload fields unchanged
- **Breaking changes:** None
- **Migration:** Uses existing `index_jobs` table
- **Rollback strategy:** Revert squash merge; in-flight Celery jobs may complete harmlessly

## 4) Acceptance Criteria (AC)

- [x] AC-01: Library upload creates `index_jobs` row and dispatches Celery task
- [x] AC-02: `DocumentIntelligenceService.process(document_id, purpose="library")` uses Mistral when native is thin/empty
- [x] AC-03: Azure DI remains `enabled_in_prod=false` in OCR meta; Library uses Mistral not DI
- [x] AC-04: Golden-corpus CER gate fails CI on extract merge regression
- [x] AC-05: `/meta/ocr-providers` reports library Mistral usage honestly

## 5) Testing Evidence

- [x] `pytest tests/unit/test_document_intelligence_service.py`
- [x] `pytest tests/unit/test_index_job_service.py`
- [x] `pytest tests/unit/test_document_index_tasks.py`
- [x] `pytest tests/unit/test_library_extraction_cer_gate.py`
- [x] `pytest tests/unit/test_ocr_ops_meta.py`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Upload with Celery unavailable falls back to synchronous index job processing
- [x] CUJ-02: Thin native PDF triggers Mistral merge path in unit tests
- [x] CUJ-03: Reprocess endpoint queues `reindex` job

## 7) Observability & Ops

- Index job status via `GET /api/v1/documents/index-jobs/{id}`
- Celery task: `process_document_index_job`
- OCR meta: `library_documents` block on `/api/v1/meta/ocr-providers`

## 8) Release Plan

1. Draft PR → CI green
2. Staging: upload scanned PDF, confirm `processing` → `indexed`/`approved`/`failed` honesty
3. Verify Celery worker registers `document_index_tasks`

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA; stale index jobs remain queryable

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: Contracts
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [x] Gate 4: Canary (N/A ok)
- [ ] Gate 5: Production verification plan
