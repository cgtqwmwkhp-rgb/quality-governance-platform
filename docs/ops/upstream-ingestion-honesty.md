# Upstream ingestion honesty (ops)

**Owner:** Platform Engineering  
**Audience:** On-call, import operators, auditors configuring templates  
**Status:** Honesty lock (docs-only) — no runtime scheduler claim

Short reference for what upstream paths **actually do today**, and what operators must **not** assume.

---

## Paths that exist

| Path | What it is | What it is not |
|------|------------|----------------|
| **XML import** | Upload/parse `.xml` layouts into audit **templates** (`xml_import` routes / `xml_importer_service`). Deterministic structure ingest. | Not OCR. Not a live schedule of audit runs. |
| **OCR / AI import** | External audit pack ingest: native extract and/or Mistral OCR → optional analysis/review → Import Review → promote findings. Gated by `EXTERNAL_AUDIT_IMPORT_ENABLED` + provider keys. | Not auto-enablement of Azure DI (E4). Not a fake “always on” AI pipeline when keys/`/readyz` say otherwise. |
| **AI templates** | Gemini (`gemini_ai` breaker) prompt→template assistance for authors. | Not a recurrence engine. Does not schedule audits from `frequency`. |

Circuit identities and degraded banners: [`docs/architecture/upstream-circuit-breakers.md`](../architecture/upstream-circuit-breakers.md).  
OCR readiness honesty: [`docs/ops/ocr-provider-readiness.md`](ocr-provider-readiness.md).

---

## Template `frequency` ≠ live scheduler

Audit templates carry an optional `frequency` field (`daily|weekly|monthly|quarterly|annually|ad_hoc`).

| Assume | Do not assume |
|--------|----------------|
| Metadata / planning hint for humans and reporting | That setting `frequency` creates cron jobs, calendar series, or automatic audit runs |
| Roadmap item **R12** (*Scheduled audit recurrence*) is the intended future engine | That XML import, OCR/AI import, or AI templates already implement R12 |

Until a recurrence engine ships and is documented as live, **operators schedule and start audits explicitly**. Empty or populated `frequency` does not change runtime scheduling behaviour.

---

## Operator assumptions (checklist)

1. **Import failures / `not_configured`:** Trust meta/`/readyz` honesty — missing keys mean the provider path is off; do not invent enablement.
2. **Degraded upstream:** Prefer Import Review banner + `upstream.degraded` — OPEN circuits fail-fast; do not retry-spam providers.
3. **XML vs OCR:** Choose XML for structured template layouts; choose OCR/AI import for scanned/external packs. They are separate CUJs.
4. **`frequency` on a template:** Treat as label only until R12 recurrence is delivered.
5. **E4 / Azure DI:** Configured ≠ enabled in prod. Do not flip DI from ops docs alone.

---

## Related

- Roadmap R12: [`docs/product/roadmap.md`](../product/roadmap.md) (scheduled audit recurrence — future)
- Partner / webhook upstream (separate lane): [`docs/ops/partner-webhooks.md`](partner-webhooks.md)
