# Change Ledger (CL-CUJ-O14-PINECONE-BULK)

**Path claim:** `feat/cuj-o14-pinecone-bulk`

## File allowlist (exclusive)

- `src/domain/models/document.py`
- `src/domain/services/index_job_service.py`
- `src/api/routes/documents.py`
- `src/infrastructure/tasks/document_index_tasks.py` (unchanged — reuses existing task)
- `alembic/versions/20260719_index_job_document_progress.py`
- `tests/unit/test_index_job_service.py`
- `docs/runbooks/PINECONE_BULK_REPROCESS_RUNBOOK.md`
- `scripts/governance/pr_body_cuj_o14_pinecone_bulk.md`

**Out of scope:** Campaign UI, UVDB, audit modules, deploy workflow changes (#1144 is complementary).

## 1) Summary

- **Feature / Change name:** O-14 — Bulk Pinecone reprocess + runbook
- **User goal:** HSEQ/platform can bulk-reprocess library documents into Pinecone with documented ops procedures, extending existing `index_jobs` infrastructure.
- **In scope:** Admin-gated bulk API, document-level job progress, resume helper, runbook, unit tests
- **Out of scope:** Full Pinecone namespace wipe, parallel indexing system, Celery deploy config (#1144)
- **Feature flag / kill switch:** Requires explicit `document_ids`, `confirm_full_tenant=true`, or `resume_from_job_id`; sync fallback when Celery unavailable (existing pattern)

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Bulk reprocess | Not available | `POST /api/v1/documents/admin/bulk-reprocess` (`admin:manage`) |
| Job progress | Chunk counters only | Document counters on `index_jobs` + enriched `GET /index-jobs/{id}` |
| Resume | Manual ID lists | `resume_from_job_id` on bulk endpoint |
| Vector preflight | Implicit at upsert time | `vector_index_configured` + warning on trigger and status |
| Ops docs | None for bulk Pinecone | `docs/runbooks/PINECONE_BULK_REPROCESS_RUNBOOK.md` |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive API + nullable-default migration columns on `index_jobs`
- **Breaking changes:** None (`IndexJobResponse` adds fields; clients tolerant)
- **Migration:** `20260719_index_job_doc_prog` adds `documents_processed/succeeded/failed`
- **Rollback strategy:** Revert commit; in-flight jobs remain queryable; no vector namespace wipe

## 4) Acceptance Criteria (AC)

- [x] AC-01: Admin bulk endpoint creates `job_type=bulk` row and dispatches existing Celery task
- [x] AC-02: Full-tenant sweep requires `confirm_full_tenant=true` (no silent wipe)
- [x] AC-03: Missing Voyage/Pinecone keys reported honestly (`vector_index_configured: false`)
- [x] AC-04: Document-level progress on job status endpoint
- [x] AC-05: Resume from failed/partial job via `resume_from_job_id`
- [x] AC-06: Runbook covers trigger, monitor, fail, resume
- [x] AC-07: Unit tests for bulk job path

## 5) Testing Evidence

- [x] `pytest tests/unit/test_index_job_service.py`
- [ ] CI green — pending parent PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Bulk job with explicit `document_ids` creates and resolves tenant-scoped IDs
- [x] CUJ-02: Full-tenant rejected without `confirm_full_tenant`
- [x] CUJ-03: Resume merges failed + remaining document IDs
- [x] CUJ-04: `vector_index_configured()` honest when keys missing
- [x] CUJ-05: `process_job` updates document progress counters

## 7) Observability & Ops

- Job status: `GET /api/v1/documents/index-jobs/{id}` (document + chunk counters, `error_log`, vector warning)
- Celery task: `process_document_index_job` (unchanged)
- Runbook: `docs/runbooks/PINECONE_BULK_REPROCESS_RUNBOOK.md`
- **Dependency:** [#1144](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1144) aligns Celery worker vector env with API — not required for API/local sync fallback; recommended before prod bulk async upsert

## 8) Release Plan

1. Merge after CI green
2. Run Alembic migration on staging
3. Execute runbook staging checklist (2–3 documents)
4. Confirm Celery worker has vector keys (post-#1144 or manual env)

## 9) Rollback Plan

1. Revert squash commit
2. Migration downgrade optional (columns are additive with server defaults)
3. In-flight Celery jobs may complete harmlessly

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation by parent agent

---

# Gate Checklist (must be complete before merge)

- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: Contracts (additive API fields)
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [x] Gate 4: Canary (N/A ok)
- [ ] Gate 5: Production verification plan
