# Upstream Circuit Breakers (Path-to-10 Preferred S10)

**Owner:** Platform Engineering  
**Classification:** Internal (C2)  
**Status:** Foundation + `/readyz` degraded aggregate + Import Review banner + Azure Blob + Mistral OCR + Gemini review + Gemini AI templates call-sites

---

## Purpose

Preferred Stage 10 (Upstream) needs a **single catalog** of named circuit breakers for OCR, AI review, and blob dependencies so:

- Call sites share stable breaker identities (`mistral_analysis`, `gemini_ai`, `gemini_review`, `blob_storage`)
- Ops and UI can surface **degraded mode** without inventing secrets or probing providers from `/readyz`
- `/readyz` exposes an informational `upstream.degraded` aggregate for banners and ops (does **not** fail the probe)

---

## Module

| Attribute | Detail |
|-----------|--------|
| **Location** | [`src/domain/services/upstream_circuit_breaker.py`](../../src/domain/services/upstream_circuit_breaker.py) |
| **Underlying primitive** | [`src/infrastructure/resilience/circuit_breaker.py`](../../src/infrastructure/resilience/circuit_breaker.py) (`CircuitBreaker`) |
| **Unit tests** | [`tests/unit/test_upstream_circuit_breaker.py`](../../tests/unit/test_upstream_circuit_breaker.py) |

### Catalog defaults

| Name | Role | `failure_threshold` | `recovery_timeout` |
|------|------|--------------------:|-------------------:|
| `mistral_analysis` | OCR | 5 | 300 s |
| `gemini_ai` | AI templates | 5 | 60 s |
| `gemini_review` | AI review | 5 | 300 s |
| `blob_storage` | Blob I/O | 5 | 60 s |

Defaults match existing OCR/AI call-site breakers where those already exist. Unknown names raise `KeyError` so callers cannot invent silent identities.

### API surface

| Function | Behaviour |
|----------|-----------|
| `get_upstream_breaker(name)` | Return registry instance or create from Preferred spec |
| `ensure_upstream_breakers_registered()` | Eagerly register the catalog (no provider dial) |
| `list_upstream_breaker_health(register_missing=…)` | Health rows; `register_missing=False` keeps cold processes honest (`unregistered`) |
| `upstream_degraded_summary()` | Banner payload: `degraded`, `open_circuits`, `half_open_circuits`, `message` |
| `call_via_upstream_breaker(name, func, …)` | Async wrapper; raises `CircuitBreakerOpenError` when open |

---

## Behaviour

```
CLOSED ──(threshold failures)──► OPEN ──(recovery_timeout)──► HALF_OPEN
   ▲                                                           │
   └──────────────────── probe success ────────────────────────┘
                         probe failure → OPEN
```

- **OPEN** → fail-fast; no outbound OCR/AI/blob call.
- **HALF_OPEN** → limited probes (`half_open_max_calls`, default 1).
- **Degraded** = any Preferred breaker in OPEN or HALF_OPEN.
- This foundation **does not** fail `/readyz` and **does not** invent SMTP/API keys.
- `/readyz` `upstream.degraded.affects_readiness` is always `false` (informational).

---

## `/readyz` aggregate

| Attribute | Detail |
|-----------|--------|
| **Helper** | [`src/infrastructure/upstream/degraded_status.py`](../../src/infrastructure/upstream/degraded_status.py) |
| **Field** | `upstream.degraded` on root `/readyz` and API `/api/v1/health/readyz` (`checks.upstream.degraded`) |
| **Honesty** | `register_missing=False`; cold processes report `unregistered`; no provider dial |

---

## Frontend degraded banner

| Attribute | Detail |
|-----------|--------|
| **Component** | [`frontend/src/components/UpstreamDegradedBanner.tsx`](../../frontend/src/components/UpstreamDegradedBanner.tsx) |
| **Mount** | External Audit Import Review (OCR/AI CUJ) |

The banner accepts controlled `openCircuits` / `halfOpenCircuits` props, or optionally polls public `/readyz` preferring `upstream.degraded` (falls back to `upstream.ai.circuits`). Missing/unregistered circuits do not show as degraded.

---

## Azure Blob call-site

| Attribute | Detail |
|-----------|--------|
| **Module** | [`src/infrastructure/storage.py`](../../src/infrastructure/storage.py) (`AzureBlobStorageService`) |
| **Ops wrapped** | `upload` / `download` / `delete` via `call_via_upstream_breaker("blob_storage", …)` |
| **Local FS** | `LocalFileStorageService` unchanged (dev path; no Preferred breaker) |
| **Readyz** | [`storage_status.py`](../../src/infrastructure/upstream/storage_status.py) surfaces `circuits.blob_storage` + skipped ping (no Azure dial) |

---

## Mistral OCR/analysis call-site

| Attribute | Detail |
|-----------|--------|
| **Module** | [`src/domain/services/mistral_analysis_service.py`](../../src/domain/services/mistral_analysis_service.py) |
| **Ops wrapped** | `analyze_text` Chat completions via `call_via_upstream_breaker("mistral_analysis", …)` |
| **Secrets** | Uses existing `settings.mistral_api_key` only; never invents keys; unconfigured stays `not_configured` |
| **Readyz** | [`ai_status.py`](../../src/infrastructure/upstream/ai_status.py) still reports honest config + circuit metadata without dialing Mistral |

---

## Gemini review call-site

| Attribute | Detail |
|-----------|--------|
| **Module** | [`src/domain/services/gemini_review_service.py`](../../src/domain/services/gemini_review_service.py) |
| **Ops wrapped** | Multimodal `review` via `call_via_upstream_breaker("gemini_review", …)` |
| **Secrets** | Uses existing `settings.google_gemini_api_key` / `GOOGLE_GEMINI_API_KEY` only; never invents keys; unconfigured stays `not_configured` |
| **Readyz** | [`ai_status.py`](../../src/infrastructure/upstream/ai_status.py) still reports honest config + circuit metadata without dialing Gemini |

---


## Gemini AI templates call-site

| Attribute | Detail |
|-----------|--------|
| **Module** | [`src/domain/services/gemini_ai_service.py`](../../src/domain/services/gemini_ai_service.py) |
| **Ops wrapped** | Template intelligence prompts via `call_via_upstream_breaker("gemini_ai", …)` |
| **Secrets** | Uses existing `GOOGLE_GEMINI_API_KEY` / env only; never invents keys; unconfigured stays unavailable without registering the breaker |
| **Readyz** | [`ai_status.py`](../../src/infrastructure/upstream/ai_status.py) still reports honest config + circuit metadata without dialing Gemini |

---

## Adoption notes

1. Prefer `get_upstream_breaker` / `call_via_upstream_breaker` for **new** upstream call sites.
2. Catalog facade call sites now cover blob Azure I/O, Mistral analysis, Gemini review, and Gemini AI templates; `get_upstream_breaker` reuses the shared registry entry.
3. Do not invent secrets or live-ping providers from readiness; keep `/readyz` honesty (`register_missing=False`).

---

## Related

- [`docs/architecture/resilience-patterns.md`](resilience-patterns.md) — general circuit breaker catalog (D05)
- [`src/infrastructure/upstream/ai_status.py`](../../src/infrastructure/upstream/ai_status.py) — OCR/AI readiness honesty + circuit metadata
- [`src/infrastructure/upstream/storage_status.py`](../../src/infrastructure/upstream/storage_status.py) — Blob readiness honesty + Preferred circuit metadata
- [`src/infrastructure/upstream/degraded_status.py`](../../src/infrastructure/upstream/degraded_status.py) — Preferred degraded aggregate for `/readyz`
- [`docs/api/error-catalog.md`](../api/error-catalog.md) — `CIRCUIT_BREAKER_OPEN` mapping guidance
