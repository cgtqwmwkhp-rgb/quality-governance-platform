# OCR artifacts, dispute, and acknowledgement stubs (R5)

Page-level OCR artifact persistence and human override stubs for external audit import. **No OCR provider dial** from these endpoints.

## Scope (v1)

| Capability | Status |
|------------|--------|
| `ocr_artifacts` table | Migration `20260717_ocr_artifacts` |
| Page consensus persist hook | `build_page_consensus(..., persist_hook=...)` + `OCRArtifactService.persist_page_consensus` |
| Dispute / ack stubs | `POST .../ocr-artifacts/dispute`, `POST .../ocr-artifacts/ack` |
| Meta / readyz flags | `capabilities.*` on `/ocr-providers` and `/readyz` |

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/api/v1/health/meta/ocr-capabilities` | GET | R5 capability flags (no secrets) |
| `/api/v1/health/meta/ocr-artifacts/dispute` | POST | Record human dispute on artifact row |
| `/api/v1/health/meta/ocr-artifacts/ack` | POST | Record human acknowledgement |

Mounted under `/api/v1/health/meta/` via `health.py` → `ocr_ops.py` (same pattern as W4 `#1010`).

## `ocr_artifacts` columns

| Column | Description |
|--------|-------------|
| `provider` | OCR engine identifier (e.g. `mistral`, `azure_document_intelligence`) |
| `page_number` | 1-indexed page |
| `content_hash` | SHA-256 of normalized text (no raw text stored) |
| `confidence` | Derived from consensus agreement + tier |
| `pipeline_version` | e.g. `2026.07.r5` |
| `job_ref` / `draft_ref` | External audit import linkage (`import_job:123`, `draft:456`) |
| `tier` | `canonical` (selected) or `advisory` (alternate provider) |
| `override_*` | Human dispute/ack metadata |

## E4 explicit non-goal

- **Do not** enable Azure Document Intelligence in production from this lane.
- Dispute/ack stubs **never** re-run Mistral, Gemini, or Azure DI.
- `azure_di.enabled_in_prod` remains `false` in all meta responses until E4 sign-off.

## Runbook

1. **Consensus not persisting:** Ensure import path calls `OCRArtifactService.persist_page_consensus` or passes `persist_hook` to `build_page_consensus`.
2. **Dispute returns 404:** Artifact id must exist in `ocr_artifacts` (migration applied).
3. **Provider unchanged after dispute:** Expected — stubs record override only; no provider dial.

## Fixtures

- `tests/fixtures/ocr/artifact_persist.json` — golden persist scenario
- `tests/fixtures/ocr/capabilities.json` — capability flag contract
