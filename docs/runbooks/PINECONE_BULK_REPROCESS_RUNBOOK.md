# Pinecone bulk reprocess runbook (O-14)

Operators use this runbook to bulk-reprocess tenant library documents through the existing `index_jobs` + Celery pipeline (OCR → chunk → Voyage embed → Pinecone upsert).

## Prerequisites

| Check | Command / endpoint |
|-------|-------------------|
| Admin JWT with `admin:manage` | Obtain from tenant admin login |
| Tenant context on token | `tenant_id` must be set on the caller |
| Vector keys (for Pinecone upsert) | `VOYAGE_API_KEY`, `PINECONE_API_KEY` (+ optional `PINECONE_HOST`, `PINECONE_INDEX`) |
| Celery worker (async path) | Worker registers `process_document_index_job` |
| API health | `GET /api/v1/health` |

Honest behaviour when vector keys are missing: jobs still rebuild chunks and AI metadata, but documents remain `approved` with `indexing_error` noting vector indexing is unavailable. The API response includes `vector_index_configured: false`.

**Deployment note:** PR [#1144](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1144) passes Voyage/Pinecone env vars to Celery worker/beat apps in staging/production. Until that merges, workers may lack vector keys even when the API has them — bulk jobs will still run but Pinecone upsert may fail on the worker.

## Trigger

### Option A — Explicit document IDs (recommended)

```bash
curl -sS -X POST "$BASE/api/v1/documents/admin/bulk-reprocess" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": [101, 102, 103]}'
```

### Option B — Full tenant sweep (requires explicit consent)

Reprocesses up to `limit` active, latest-version documents in statuses: `indexed`, `approved`, `published`, `active`, `failed`.

```bash
curl -sS -X POST "$BASE/api/v1/documents/admin/bulk-reprocess" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirm_full_tenant": true, "limit": 500}'
```

### Option C — Resume a partial/failed job

```bash
curl -sS -X POST "$BASE/api/v1/documents/admin/bulk-reprocess" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_from_job_id": 42}'
```

Response fields:

- `index_job_id` — poll status via `GET /api/v1/documents/index-jobs/{id}`
- `dispatched` — `true` when Celery accepted the task; `false` when synchronous fallback ran
- `vector_index_configured` / `vector_index_warning` — preflight honesty

## Monitor

```bash
JOB_ID=42
curl -sS "$BASE/api/v1/documents/index-jobs/$JOB_ID" \
  -H "Authorization: Bearer $TOKEN" | jq
```

Key progress fields:

| Field | Meaning |
|-------|---------|
| `status` | `pending` → `processing` → `completed` / `failed` |
| `documents_total` | Documents in scope |
| `documents_processed` | Documents finished (success or failure) |
| `documents_succeeded` | Documents that completed the pipeline |
| `documents_failed` | Documents with extraction or missing-file errors |
| `chunks_*` | Chunk-level embed/upsert progress |
| `error_log` | Per-document failures with timestamps |
| `vector_index_configured` | Whether upsert keys are present on the API process |

Celery (when async):

```bash
celery -A src.infrastructure.tasks.celery_app inspect active
celery -A src.infrastructure.tasks.celery_app inspect registered | grep process_document_index_job
```

## Failure handling

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `vector_index_configured: false` | Missing Voyage/Pinecone keys on API or worker | Set keys; redeploy worker after #1144 |
| `dispatched: false` | Celery broker unavailable | Job ran synchronously in API process — check broker; re-trigger if timed out |
| `Document N: no searchable text extracted` | OCR/extraction failure | Fix source file or OCR keys; resume with `resume_from_job_id` |
| `Document N not found` | Stale ID in job | Remove ID and re-trigger subset |
| Job `failed` with partial `documents_succeeded` | Some docs failed | Status may still be `completed` when partial — inspect `error_log` |
| Worker upsert errors in logs | Pinecone host/index mismatch | Verify `PINECONE_HOST` or legacy index/env construction |

Reindex semantics: each document deletes existing `document_chunks` rows and re-upserts vectors per document (`doc_{id}_chunk_{index}`). This is per-document reindex, not a full Pinecone namespace wipe.

## Resume

1. Note the failed job ID from the trigger response or DB (`index_jobs`).
2. Call bulk reprocess with `{"resume_from_job_id": <id>}`.
3. Resume includes documents after `documents_processed` plus any IDs listed in `error_log`.
4. Poll the new job until `documents_processed == documents_total`.

## Single-document reprocess

For one-off fixes, use the existing endpoint (requires `document:update`, not admin):

```bash
curl -sS -X POST "$BASE/api/v1/documents/{document_id}/reprocess" \
  -H "Authorization: Bearer $TOKEN"
```

## Database inspection (optional)

```sql
SELECT id, job_type, status, documents_processed, documents_succeeded, documents_failed,
       jsonb_array_length(document_ids::jsonb) AS documents_total,
       started_at, completed_at
FROM index_jobs
ORDER BY id DESC
LIMIT 10;
```

## Staging verification checklist

- [ ] Trigger bulk reprocess for 2–3 known documents
- [ ] Confirm `index_job_id` returned and `dispatched: true` when Celery is up
- [ ] Poll until `status=completed`
- [ ] Spot-check document rows: `indexed_at` updated, `indexing_error` null when vectors configured
- [ ] Run semantic search smoke test on reindexed content
- [ ] Repeat with vector keys unset — confirm honest warning, no fake `indexed` status without upsert
