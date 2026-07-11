# Upstream Circuit Breakers (Path-to-10 Preferred S10)

**Owner:** Platform Engineering  
**Classification:** Internal (C2)  
**Status:** Foundation (library + degraded UX banner)

---

## Purpose

Preferred Stage 10 (Upstream) needs a **single catalog** of named circuit breakers for OCR, AI review, and blob dependencies so:

- Call sites share stable breaker identities (`mistral_analysis`, `gemini_ai`, `gemini_review`, `blob_storage`)
- Ops and UI can surface **degraded mode** without inventing secrets or probing providers from `/readyz`
- Future wiring can migrate ad-hoc per-service breakers onto one facade without renaming circuits already reported under `upstream.ai.circuits`

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

---

## Frontend degraded banner

| Attribute | Detail |
|-----------|--------|
| **Component** | [`frontend/src/components/UpstreamDegradedBanner.tsx`](../../frontend/src/components/UpstreamDegradedBanner.tsx) |
| **Mount** | External Audit Import Review (OCR/AI CUJ) |

The banner accepts controlled `openCircuits` / `halfOpenCircuits` props, or optionally polls public `/readyz` for `upstream.ai.circuits[*].state` when `pollReadyz` is enabled. Missing/unregistered circuits do not show as degraded.

---

## Adoption notes

1. Prefer `get_upstream_breaker` / `call_via_upstream_breaker` for **new** upstream call sites.
2. Existing services that already construct `CircuitBreaker("mistral_analysis" | …)` remain compatible: `get_upstream_breaker` reuses the shared registry entry.
3. Wire deeper call-site migration and any `/readyz` aggregate field in a follow-up lane if contested with other readiness PRs.

---

## Related

- [`docs/architecture/resilience-patterns.md`](resilience-patterns.md) — general circuit breaker catalog (D05)
- [`src/infrastructure/upstream/ai_status.py`](../../src/infrastructure/upstream/ai_status.py) — OCR/AI readiness honesty + circuit metadata
- [`docs/api/error-catalog.md`](../api/error-catalog.md) — `CIRCUIT_BREAKER_OPEN` mapping guidance
