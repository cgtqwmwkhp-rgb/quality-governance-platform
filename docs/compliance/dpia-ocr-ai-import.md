# Data Protection Impact Assessment (DPIA) — OCR / AI Document and Case Processing

**Document ID:** DPIA-QGP-OCR-AI-2026-001  
**Platform:** Quality Governance Platform (QGP)  
**Version:** 2.0  
**Status:** Body complete — **re-review required**: v2.0 adds processors that were already live in production and undisclosed (Anthropic, OpenAI, Voyage AI, Pinecone, Azure AI Document Intelligence). DPO residual-risk acceptance (EA-03) was recorded against v1.0, which covered Mistral and Gemini only.  
**Owner:** Privacy / Platform Engineering  
**Related:** [`../privacy/dpia-template.md`](../privacy/dpia-template.md), [`../privacy/dpia-checklist.md`](../privacy/dpia-checklist.md), [`../privacy/dpia-incidents.md`](../privacy/dpia-incidents.md), [`dpia-quality-governance-platform.md`](dpia-quality-governance-platform.md), [`e4-dual-ocr-redaction-gate.md`](e4-dual-ocr-redaction-gate.md)

---

## 1. Necessity (UK GDPR Art. 35)

Three distinct flows send tenant content to third-party AI processors:

1. **External audit import** — tenant audit PDF/image documents go out for OCR and structured extraction.
2. **Governance library indexing** — uploaded library documents are OCR'd, chunked, analysed, **embedded, and the resulting vectors plus verbatim chunk previews are stored in a vendor-hosted vector database**.
3. **AI-assisted case analysis** — incident, near-miss and audit text is sent to a general-purpose LLM for corrective-action recommendations, analyst notes, audit generation/challenge and ISO analysis.

Content may contain employee names, site contacts, vehicle identifiers, injury narratives, and other personal / special-category data.

The combination of **multiple third-country processors**, **large-scale document egress**, **persistent third-party retention of document-derived content** (flow 2), and **possible special-category content** meets the Art. 35 threshold. This DPIA is the Path-to-10 S15 compliance artifact for all three flows.

**v2.0 scope correction.** v1.0 assessed only Mistral and Gemini. The data controller confirmed in writing on 2026-07-28 that Anthropic, OpenAI, Voyage AI and Pinecone are also enabled and in use in production, and Azure AI Document Intelligence is enabled (`azure_di.enabled_in_prod=true`) under the closed [E4 gate](e4-dual-ocr-redaction-gate.md). Those processors were processing before they were documented; this version states that plainly rather than presenting them as prospective.

---

## 2. Processing summary

| Field | Description |
| --- | --- |
| **Name** | Document OCR, AI analysis, semantic indexing, and AI-assisted case analysis |
| **Purpose** | Extract findings, clauses, evidence hints and review drafts; make library documents semantically searchable; assist humans on incident / audit records |
| **Controller** | Tenant organisation (customer) for their corpus; Plantexpand operates QGP as processor / joint controller per DPA schedule |
| **Data subjects** | Employees, contractors, auditors, site contacts, injured persons, and other individuals named in imported packs, library documents, or case records |
| **Systems** | `MistralOCRService`, `MistralAnalysisService`, `GeminiReviewService`, `AzureDocumentIntelligenceClient`, `ExternalAuditImportService`, `DocumentIntelligenceService`, `DocumentAIService`, `EmbeddingService`, `VectorSearchService`, `IndexJobService`, `GovernedKnowledgeService`, `SafetyInsightsAnalyst`, `RecommendationEngine`, blob storage for source files |

### 2.0a Sub-processors (all confirmed live in production unless stated)

Published machine-readable equivalent: `GET /api/v1/privacy/data-processing-register` → `subprocessors`. Provider ↔ credential linkage SSOT: [`src/core/ai_provider_disclosure.py`](../../src/core/ai_provider_disclosure.py).

| Processor | Role | What it actually receives | Retention posture | Region / transfer mechanism |
| --- | --- | --- | --- | --- |
| Mistral AI | OCR + structured extraction | External audit document bytes / page images; library document bytes when native extraction is thin or empty; extracted text for analysis | Transient — returns a result; nothing stored by QGP | **Unknown** — not established in repo |
| Google Gemini | Multimodal review | External audit document bytes for second-pass review | Transient | **Unknown** |
| Azure AI Document Intelligence | Dual-OCR / library OCR failover | Library and external-audit document bytes when Mistral/native OCR is thin or fails | Transient | **UK South** — the [E4 gate](e4-dual-ocr-redaction-gate.md) records a dedicated `qgp-docintel` resource in `uksouth`, confirmed in UK South by live resource enumeration on 2026-07-28; the deployed `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` value is not verifiable from the repository |
| Anthropic | Document + case analysis (preferred shared AI client) | Library document text (≤50k chars per analysis), incident descriptions, aggregated incident/near-miss themes with case reference numbers, audit finding and clause text | Transient | **Unknown** |
| OpenAI | Fallback LLM on shared AI client paths | Same prompt content as Anthropic when selected by `AI_PROVIDER` / key precedence | Transient | **Unknown** |
| Voyage AI | Embeddings | Full text of **every** library document chunk at index time; user search query text | Transient — returns vectors | **Unknown** |
| **Pinecone** | **Vector database — stores content** | Embedding vectors per chunk **plus metadata containing the first 200 characters of each chunk verbatim**, `document_id`, `tenant_id`, `chunk_index`, heading, page number, document type | **Retains** until QGP deletes by vector ID | **Unknown** — index `qgp-documents`, serverless environment identifier in config does not resolve to a country in the repository |
| Genspark.ai | Legacy shared-AI-client fallback | Prompt content when selected | Transient | **Unknown**; activation not confirmed by controller |
| Perplexity | Horizon scanning / audit-builder research | Research query text derived from document titles and topics | Transient | **Unknown**; activation not confirmed by controller |

**Why "unknown" and not a mechanism.** No vendor DPA, SCC or UK IDTA artifact exists in this repository for any of these AI processors, and no client in the codebase pins a processing region. Writing "UK South" or "SCC via vendor DPA" for them would make the register confidently false. The controller must establish each vendor's processing location and safeguard and record it here. The single exception is Azure AI Document Intelligence, whose UK South region is claimed on the E4 gate's documented resource — that claim is sourced, not assumed.

**Pinecone is materially more serious than the others.** Mistral, Gemini, Azure DI, Anthropic, OpenAI and Voyage receive content, return a result, and hold nothing on QGP's behalf. Pinecone is a **persistent transfer**: document-derived content — including verbatim text previews — sits in a vendor-hosted index until QGP deletes it, which brings storage-limitation, erasure and international-transfer obligations that transient processing does not.

### 2.1 Lawful basis

| Basis | Application |
| --- | --- |
| **Art. 6(1)(f) legitimate interests** | Quality / H&S assurance and ISO evidence efficiency — balanced against data-subject rights; human review before promotion |
| **Art. 6(1)(c) legal obligation** | Where import supports statutory H&S / ISO conformity evidence retention |
| **Art. 9 (special category)** | Only where free text / images contain health or similar data; rely on Art. 9(2)(b) employment / H&S obligations **or** do not send that content to AI (minimise / redact first) |

---

## 3. Data flow

### 3.1 External audit import (transient egress)

```
Tenant uploads audit PDF/image
        │
        ▼
Azure Blob (tenant-scoped storage key)
        │
        ├──► Mistral OCR (api.mistral.ai) — when native text extraction fails / image-heavy
        ├──► Mistral Chat JSON analysis — structured findings extraction
        ├──► Azure AI Document Intelligence — dual-OCR / failover when OCR is thin or fails
        └──► Gemini multimodal review — optional second-pass visual review
        │
        ▼
Import draft / review workspace (human-in-the-loop)
        │
        ▼
Promotion to tenant records (audits, findings, CAPA, risks) — no auto-live findings from provider failure paths
```

The Azure Blob storage that holds source files (container `evidence-assets`) is in **West Europe**,
not UK South — UK/EEA, so no third-country transfer, but see platform DPIA §2.2a and
[`gdpr-compliance.md`](gdpr-compliance.md) §7.1. Corrected 2026-07-28.

### 3.2 Governance library indexing (persistent egress — third-party retention)

`IndexJobService.process_job` (Celery) runs per library document:

```
Library upload (POST /api/v1/documents) ──► Azure Blob + documents row
        │
        ▼
DocumentIntelligenceService: native extraction ──► Mistral OCR ──► Azure DI failover
        │
        ▼
DocumentAIService.analyze_document ──► Anthropic (or OpenAI / Genspark via shared client)
        │                                  sends up to 50k chars of document text
        ▼
generate_chunks ──► document_chunks rows (full chunk text, PostgreSQL)
        │
        ▼
EmbeddingService ──► Voyage AI  (sends FULL text of every chunk)
        │
        ▼
VectorSearchService.upsert_chunks ──► Pinecone index `qgp-documents`
        │        vector + metadata { document_id, tenant_id, chunk_index,
        │        heading, page_number, document_type, content_preview[:200] }
        ▼
GovernedKnowledgeService.map_document_to_schemes ──► shared AI client (document text)
```

Read path: `GET /api/v1/documents/search/semantic` and governed-KB evidence lookup send the **query text** to Voyage and the resulting **query vector** to Pinecone with a `tenant_id` metadata filter.

Delete path: `IndexJobService.delete_pending_stale_vectors` (superseded generations) and `document_library_disposal_service` (library disposal) delete by explicit vector ID. A failed delete is logged as an error and **not automatically retried**, so content can remain in the vendor index after QGP believes it is gone.

**Index scope (established by code reading).** `Document` rows are created in exactly one place — the library upload route (`src/api/routes/documents.py`) — and only `IndexJobService` upserts vectors. Incident, near-miss, RTA, complaint and audit-finding records are **not** indexed and never reach Pinecone as records. The residual exposure is indirect: a document uploaded *into the library* may itself be a case report, in which case its text and previews are indexed like any other document.

### 3.3 AI-assisted case analysis (transient egress of case content)

```
Incident / near-miss / audit records (PostgreSQL)
        │
        ├──► RecommendationEngine.get_corrective_action_recommendations ──► Anthropic (incident description verbatim)
        ├──► SafetyInsightsAnalyst.synthesize_analyst_note ──► Anthropic (theme labels + case reference numbers + KPI ratios)
        ├──► AuditChallengePipeline / AuditBuilderGenerationPipeline ──► Anthropic
        └──► ISOComplianceService ──► shared AI client (Anthropic → OpenAI → Genspark)
```

This flow was not covered by v1.0 at all: the platform DPIA described incidents as PostgreSQL-only processing.

### 3.4 Categories that may leave the UK/EEA boundary

| Category | Examples | Egress risk | Also retained by Pinecone? |
| --- | --- | --- | --- |
| Identity | Names, roles, email in report text | High if unredacted | Yes, where it falls in the first 200 chars of a chunk or is embedded in a vector |
| Contact | Phone, site address | Medium | As above |
| Special category | Injury / health narratives in H&S audits and case records | High | Yes, where such a document is in the library |
| Operational | Findings, non-conformances, clause refs | Medium | Yes |
| Media | Page images / PDF bytes | High (full document) | No — images are not sent to Voyage/Pinecone |
| Tenant identifiers | `tenant_id`, `document_id`, reference numbers | Medium (linkability) | Yes — stored as index metadata |

---

## 4. Necessity, proportionality, and minimisation

| Control | Implementation |
| --- | --- |
| **Optional processors** | OCR/AI skipped when API keys unset (`provider_status=not_configured`); fail soft — no fabricated findings |
| **Size limits** | Gemini path rejects oversized PDFs before upload |
| **No image echo** | Mistral OCR request sets `include_image_base64: false` |
| **Circuit breakers** | Provider breakers on Mistral/Gemini/document-AI analysis paths |
| **Human gate** | Promotion to live records requires import review / operator action |
| **Tenant isolation** | Imports and blobs scoped by `tenant_id`; Pinecone queries filter on `tenant_id` metadata |
| **Logging** | Structured logs must not dump document bodies or OCR full text |
| **Vector deletion** | Deterministic vector IDs (`doc_{id}_chunk_{n}`) allow delete-by-ID on reindex and disposal — the only mechanism serverless indexes support |
| **Disclosure invariant** | `tests/unit/test_ai_provider_disclosure.py` fails the build when a provider credential exists without a register entry |

**Known minimisation gaps (not controls — open items).**

- No pre-egress redaction on any path (accepted as follow-on hardening in v1.0; still open).
- Voyage receives **full** chunk text, not a minimised extract; Pinecone metadata retains a verbatim 200-character preview per chunk. Neither is required for retrieval to function — the preview in particular is a UI convenience.
- Vector deletion failures are logged but not retried, so third-party erasure is not guaranteed by code.

**Alternatives considered:** Manual transcription only (rejected — not scalable); on-prem OCR only (deferred — cost/ops); redaction pipeline before egress (accepted as follow-on hardening).

---

## 5. Risk assessment

| Risk | Likelihood | Impact | Mitigation | Residual |
| --- | --- | --- | --- | --- |
| Unintended special-category egress to AI processor | Medium | High | DPIA + operator guidance; minimise packs; future pre-egress redaction | Medium |
| Cross-tenant leakage via mis-keyed storage | Low | Critical | Tenant-scoped keys + RLS / query filters | Low |
| Processor retention beyond need | Medium | High | DPA / processor terms; disable unused providers; no training opt-in without legal review | Medium |
| Prompt / response logging of PII | Medium | Medium | PII-filtered logging; avoid persisting raw provider payloads in app logs | Low |
| Over-automated decisioning | Low | Medium | Human-in-the-loop promotion; provider failures do not create live findings | Low |
| Sub-processor region / transfer opacity | **High** | High | Processors now named in the register with regions and mechanisms marked **unknown**; controller must establish each vendor's location and safeguard | **High — open** |
| Persistent third-party retention of document content in the vector index (incl. verbatim previews) | **Certain where the library is indexed** | High | Delete-by-ID on reindex and disposal; tenant-filtered queries; register declares the retention | **High — open** (no vendor DPA, region unknown, deletion not retried) |
| Erasure / storage-limitation not honoured in the vector index after a failed delete | Medium | High | Failure is logged as an error; stale IDs recorded on the index job | Medium — needs a retry or reconciliation job |
| Case-register free text (injury narratives) leaving the UK/EEA in AI prompts | Medium | High | Human-invoked features; rule-based fallbacks exist when keys absent | Medium — undocumented before v2.0 |
| Processors live in production before they were disclosed | **Occurred** | High | v2.0 disclosure + build-time invariant tying credentials to the register | Low going forward; the historical gap needs controller acknowledgement |

---

## 6. Data-subject rights

| Right | Path |
| --- | --- |
| Access / portability | `GET /api/v1/gdpr/me/data-export` |
| Erasure | `POST /api/v1/gdpr/me/data-erasure` (pseudonymisation) |
| Restriction | `GDPRService.restrict_processing` |
| Security / privacy contact | `GET /api/v1/privacy/contact` and `/.well-known/security.txt` |

Imported blobs under **legal hold** (`EvidenceRetentionPolicy.LEGAL_HOLD` on `evidence_assets`) must not be purged by standard retention jobs until hold is released.

---

## 7. Organisational measures (checklist)

- [ ] DPA / SCC or UK IDTA schedule lists **every** processor in §2.0a: Mistral, Google, Microsoft (Azure DI resource), Anthropic, OpenAI, Voyage AI, Pinecone (and Genspark / Perplexity if their keys are set)
- [ ] Processing region established and recorded for each AI processor — replaces the `unknown` values in the register
- [ ] Pinecone index region confirmed in the vendor console and recorded here
- [ ] ROPA entries for “External audit OCR/AI import”, “Governance library document indexing and semantic search”, and “AI-assisted analysis of case-register and audit records”
- [ ] Operators instructed not to upload packs known to contain unnecessary special-category imagery
- [x] Production keys set only after this DPIA is accepted; placeholders blocked in production config — **partially breached in practice**: keys for four processors were live before this DPIA covered them
- [ ] Decision recorded on whether the verbatim `content_preview` metadata is necessary, or should be dropped from vector metadata
- [ ] Reconciliation or retry for failed vector deletions (erasure assurance)
- [ ] Annual re-review or on material model / vendor change
- [ ] EA-03 DPO sign-off **re-confirmed against v2.0 scope** in `docs/evidence/external-attestation-tracker.md` — the recorded acceptance covered the v1.0 two-processor scope

---

## 8. Residual risk statement

v1.0 accepted residual risk of document egress as **Medium** for Mistral/Gemini, conditional on sub-processor contracts being in place before production key enablement.

v2.0 cannot carry that acceptance forward unchanged:

- the processor set is more than twice as large as the one assessed;
- one processor (**Pinecone**) **retains** document-derived content in a vendor index whose region is unknown, which v1.0 never considered;
- case-register free text reaches an AI processor, which v1.0 never considered;
- no vendor DPA / SCC / IDTA artifact exists for any AI processor.

**Residual risk for the transfers in §2.0a is therefore stated as HIGH and unaccepted, pending controller/DPO decision.** This is a documentation and disclosure statement only — no AI feature has been disabled or gated by this assessment; enablement remains the controller's decision.

| Role | Name | Date | Decision |
| --- | --- | --- | --- |
| Assessor | Platform Engineering | 2026-07-11 | v1.0 DPIA body complete (Mistral / Gemini only) |
| Assessor | Platform Engineering | 2026-07-28 | v2.0 scope corrected to the processors actually live in production |
| Data controller / accountable owner | David Harris | 2026-07-28 | Confirmed in writing that Pinecone, Voyage AI, OpenAI and Anthropic are enabled and in use in production |
| DPO / Privacy lead | _Pending — v2.0 scope_ | | Accept / reject residual risk for the expanded processor set |

---

## 9. Evidence pointers

| Item | Location |
| --- | --- |
| OCR service | `src/domain/services/mistral_ocr_service.py` |
| Mistral analysis | `src/domain/services/mistral_analysis_service.py` |
| Gemini review | `src/domain/services/gemini_review_service.py` |
| Azure DI client + readiness | `src/domain/services/azure_document_intelligence_service.py` |
| OCR provider orchestration / failover | `src/domain/services/document_intelligence_service.py` |
| Import orchestration | `src/domain/services/external_audit_import_service.py` |
| Document analysis (Anthropic) + Voyage embeddings + Pinecone client | `src/domain/services/document_ai_service.py` |
| Shared AI client precedence (Anthropic → OpenAI → Genspark) | `src/domain/services/ai_models.py` |
| Index pipeline (OCR → chunk → embed → Pinecone) | `src/domain/services/index_job_service.py` |
| Vector deletion on disposal | `src/domain/services/document_library_disposal_service.py` |
| Governed-KB retrieval / quiz generation | `src/domain/services/governed_knowledge_service.py` |
| Case-analysis AI paths | `src/domain/services/ai_predictive_service.py`, `src/domain/services/safety_insights_analyst.py`, `src/domain/services/audit_challenge_pipeline.py` |
| Provider ↔ disclosure SSOT | `src/core/ai_provider_disclosure.py` |
| Disclosure invariant tests | `tests/unit/test_ai_provider_disclosure.py` |
| Config guardrails | `src/core/config.py` (`mistral_*`, `google_gemini_api_key`, `azure_document_intelligence_*`, `anthropic_api_key`, `openai_api_key`, `voyage_api_key`, `pinecone_*`) |
| Privacy contact API | `GET /api/v1/privacy/contact` |
| security.txt | `GET /.well-known/security.txt` |
| Checklist | `docs/privacy/dpia-checklist.md` |
| Governance link | `docs/governance/privacy-ocr-ai-dpia.md` |
| **S15 unsigned attestation pack** | `docs/compliance/s15-dpia-art30-attestation-pack.md` |
| Art. 30 ROPA checklist | `docs/compliance/article-30-ropa-checklist.md` |
| EA tracker (EA-03 still open) | `docs/evidence/external-attestation-tracker.md` |
