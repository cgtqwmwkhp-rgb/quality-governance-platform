# OCR provider readiness (ops)

Machine-readable OCR configuration honesty for external audit import, library document indexing, and future dual-OCR paths.

## Endpoint

| Path | Auth | Purpose |
|------|------|---------|
| `GET /api/v1/meta/ocr-providers` | None | Canonical provider configuration flags + capability notes |
| `GET /api/v1/meta/ocr-capabilities` | None | Canonical R5 capability flags + endpoint map |
| `GET /api/v1/health/meta/ocr-providers` | None | Legacy alias (same payload) |
| `GET /api/v1/health/readyz` → `checks.ocr_providers` | None | Summary booleans for probes (`meta_endpoint` = canonical) |

## Providers reported

| Provider | Env vars (presence only) | Role |
|----------|--------------------------|------|
| **mistral** | `MISTRAL_API_KEY`, `MISTRAL_OCR_TIMEOUT_SECONDS` | Primary OCR for scanned/image-heavy imports and library index jobs |
| **gemini** | `GOOGLE_GEMINI_API_KEY` or `GEMINI_API_KEY` | Post-OCR review / analysis |
| **azure_di** | `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY`, `AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD` | Library OCR failover + Planet Mark enrichment when ENABLE_PROD |

## Library Azure DI (DS-1b — enabled after E4 DPO sign-off)

Library document OCR today uses **Mistral** only (`library_documents.ocr_configured` mirrors `MISTRAL_API_KEY` presence).

Future library dual-OCR / Azure DI requires **both**:

1. **E4 DPO sign-off** — privacy/DPIA gate before any production DI traffic.
2. **Dedicated QGP Azure Document Intelligence resource** — provision a QGP-owned Cognitive Services account/endpoint. **Do not** point QGP at the Jobsheet Document Intelligence resource.

Meta fields make this explicit:

| Field | Value (prep lane) | Meaning |
|-------|-------------------|---------|
| `providers.azure_di.enabled_in_prod` | `configured AND ENABLE_PROD` | Honest enablement after E4 sign-off |
| `providers.azure_di.used_in_library` | same as enabled_in_prod | Library DocumentIntelligenceService failover path |
| `providers.azure_di.used_in_prod` | same as enabled_in_prod | Live analyze when flag + credentials set |
| `providers.azure_di.resource_scope` | `qgp_dedicated_required` | Ops must provision QGP DI, not reuse Jobsheet |
| `providers.azure_di.jobsheet_resource_allowed` | `false` | Jobsheet DI endpoint must not be wired |
| `providers.azure_di.prod_enable_flag_set` | env presence | Reports whether ENABLE_PROD is set |
| `library_documents.azure_di_enabled_in_prod` | mirrors provider flag | Library block mirrors DI prod gate |
| `library_documents.azure_di_used` | mirrors provider flag | Library index jobs may call DI on thin/failed OCR |

## E4 DPO gate (explicit non-goal)

- Enable Azure Document Intelligence only with a **dedicated QGP** DI resource (never Jobsheet).
- `azure_di.configured` means both endpoint + key env vars are non-empty — **not** that DI is live.
- `azure_di.enabled_in_prod` is `true` only when endpoint+key are set **and** `AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD` is true.
- `AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD` defaults OFF in code; credentials alone never enable OCR.
- Meta and `/readyz` probes **never** dial Mistral, Gemini, or Azure DI.

## QGP /readyz honesty

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
    "azure_di": {
      "configured": false,
      "enabled_in_prod": false,
      "used_in_library": false,
      "resource_scope": "qgp_dedicated_required",
      "jobsheet_resource_allowed": false
    }
  },
  "library_documents": {
    "azure_di_enabled_in_prod": false,
    "azure_di_used": false
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
4. **Tempted to reuse Jobsheet DI endpoint:** Blocked by design — provision dedicated QGP DI per `resource_scope`.
