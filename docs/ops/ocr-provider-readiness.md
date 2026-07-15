# OCR provider readiness (ops)

Machine-readable OCR configuration honesty for external audit import and future dual-OCR paths.

## Endpoint

| Path | Auth | Purpose |
|------|------|---------|
| `GET /api/v1/health/meta/ocr-providers` | None | Provider configuration flags + capability notes |
| `GET /api/v1/health/readyz` → `checks.ocr_providers` | None | Summary booleans for probes |

> **Path note:** Canonical target is `/api/v1/meta/ocr-providers` (alongside `/api/v1/meta/version`). This lane mounts under `/api/v1/health/meta/` because `src/api/__init__.py` / `main.py` are outside the W4 allowlist. A follow-up PR may add a top-level alias.

## Providers reported

| Provider | Env vars (presence only) | Role |
|----------|--------------------------|------|
| **mistral** | `MISTRAL_API_KEY`, `MISTRAL_OCR_TIMEOUT_SECONDS` | Primary OCR for scanned/image-heavy imports |
| **gemini** | `GOOGLE_GEMINI_API_KEY` or `GEMINI_API_KEY` | Post-OCR review / analysis |
| **azure_di** | `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Dual-OCR consensus scaffold (not prod-enabled) |

## E4 DPO gate (explicit non-goal)

- **Do not** enable Azure Document Intelligence in production from this lane.
- `azure_di.configured` means both env vars are non-empty — **not** that DI is live.
- `azure_di.enabled_in_prod` is always `false` in meta responses until E4 sign-off.
- Meta and `/readyz` probes **never** dial Mistral, Gemini, or Azure DI.

## Jobsheet /readyz honesty

- `ocr_ping.status` = `skipped` — connectivity is `unprobed`.
- Circuit breaker metadata is included when registered in-process.
- Native PDF/DOCX/XLSX extraction remains available without OCR keys.

## Example (keys unset)

```json
{
  "status": "not_configured",
  "providers": {
    "mistral": { "configured": false, "api_key_present": false },
    "gemini": { "configured": false, "api_key_present": false },
    "azure_di": { "configured": false, "enabled_in_prod": false }
  },
  "e4_non_goal": "Azure Document Intelligence is not enabled in production..."
}
```

## Schema

See `docs/evidence/ocr-ops-status.schema.json` for the JSON Schema contract.

## R5 capabilities (artifacts + dispute stubs)

| Flag | Meaning |
|------|---------|
| `capabilities.ocr_artifacts_table` | `ocr_artifacts` migration landed |
| `capabilities.page_consensus_persist` | `build_page_consensus` persist hook available |
| `capabilities.dispute_ack_stubs` | Human override endpoints mounted |
| `capabilities.provider_dial_on_probes` | Always `false` |

See `docs/ops/ocr-artifacts-dispute-ack.md` for dispute/ack runbook.

## Runbook

1. **Import OCR failing with `not_configured`:** Check meta endpoint; set Key Vault refs for `MISTRAL_API_KEY`.
2. **Review step skipped:** Ensure `GOOGLE_GEMINI_API_KEY` is present; partial config is expected until both keys exist.
3. **Azure DI fields present but OCR unchanged:** Expected — E4 adapter is scaffold-only; no prod enablement.
