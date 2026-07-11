# Data Protection Impact Assessment (DPIA) — OCR / AI External Audit Import

**Document ID:** DPIA-QGP-OCR-AI-2026-001  
**Platform:** Quality Governance Platform (QGP)  
**Version:** 1.0  
**Status:** Complete — pending DPO residual-risk acceptance (EA-03)  
**Owner:** Privacy / Platform Engineering  
**Related:** [`../privacy/dpia-template.md`](../privacy/dpia-template.md), [`../privacy/dpia-checklist.md`](../privacy/dpia-checklist.md), [`../privacy/dpia-incidents.md`](../privacy/dpia-incidents.md), [`dpia-quality-governance-platform.md`](dpia-quality-governance-platform.md)

---

## 1. Necessity (UK GDPR Art. 35)

External audit import sends **tenant audit PDF/image documents** to third-party AI processors for OCR and structured extraction. Documents may contain employee names, site contacts, vehicle identifiers, injury narratives, and other personal / special-category data.

This combination of **new processors**, **large-scale document egress**, and **possible special-category content** meets the Art. 35 threshold. This DPIA is the Path-to-10 S15 compliance artifact for OCR/AI import.

---

## 2. Processing summary

| Field | Description |
| --- | --- |
| **Name** | External audit document OCR + AI structured analysis |
| **Purpose** | Extract findings, clauses, evidence hints, and review drafts so humans can promote curated records into QGP (audits, CAPA, risks) |
| **Controller** | Tenant organisation (customer) for their audit corpus; Plantexpand operates QGP as processor / joint controller per DPA schedule |
| **Processors (sub-processors)** | Mistral AI (OCR + chat analysis); Google Gemini (multimodal review) when configured |
| **Data subjects** | Employees, contractors, auditors, site contacts, injured persons, and other individuals named in imported audit packs |
| **Systems** | `MistralOCRService`, `MistralAnalysisService`, `GeminiReviewService`, `ExternalAuditImportService`, blob storage for source files |

### 2.1 Lawful basis

| Basis | Application |
| --- | --- |
| **Art. 6(1)(f) legitimate interests** | Quality / H&S assurance and ISO evidence efficiency — balanced against data-subject rights; human review before promotion |
| **Art. 6(1)(c) legal obligation** | Where import supports statutory H&S / ISO conformity evidence retention |
| **Art. 9 (special category)** | Only where free text / images contain health or similar data; rely on Art. 9(2)(b) employment / H&S obligations **or** do not send that content to AI (minimise / redact first) |

---

## 3. Data flow

```
Tenant uploads audit PDF/image
        │
        ▼
Azure Blob (tenant-scoped storage key)
        │
        ├──► Mistral OCR (api.mistral.ai) — when native text extraction fails / image-heavy
        ├──► Mistral Chat JSON analysis — structured findings extraction
        └──► Gemini multimodal review — optional second-pass visual review
        │
        ▼
Import draft / review workspace (human-in-the-loop)
        │
        ▼
Promotion to tenant records (audits, findings, CAPA, risks) — no auto-live findings from provider failure paths
```

### 3.1 Categories that may leave the UK/EEA boundary

| Category | Examples | Egress risk |
| --- | --- | --- |
| Identity | Names, roles, email in report text | High if unredacted |
| Contact | Phone, site address | Medium |
| Special category | Injury / health narratives in H&S audits | High |
| Operational | Findings, non-conformances, clause refs | Medium |
| Media | Page images / PDF bytes | High (full document) |

---

## 4. Necessity, proportionality, and minimisation

| Control | Implementation |
| --- | --- |
| **Optional processors** | OCR/AI skipped when API keys unset (`provider_status=not_configured`); fail soft — no fabricated findings |
| **Size limits** | Gemini path rejects oversized PDFs before upload |
| **No image echo** | Mistral OCR request sets `include_image_base64: false` |
| **Circuit breakers** | Provider breakers on Mistral/Gemini analysis paths |
| **Human gate** | Promotion to live records requires import review / operator action |
| **Tenant isolation** | Imports and blobs scoped by `tenant_id` |
| **Logging** | Structured logs must not dump document bodies or OCR full text |

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
| Sub-processor region / transfer opacity | Medium | High | Document processors in ROPA; SCCs / UK IDTA via vendor DPA; prefer UK/EU processing where offered | Medium |

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

- [ ] DPA / SCC schedule lists Mistral and Google as sub-processors (when enabled in that environment)
- [ ] ROPA entry for “External audit OCR/AI import”
- [ ] Operators instructed not to upload packs known to contain unnecessary special-category imagery
- [ ] Production keys set only after this DPIA is accepted; placeholders blocked in production config
- [ ] Annual re-review or on material model / vendor change
- [ ] EA-03 DPO sign-off recorded in `docs/evidence/external-attestation-tracker.md`

---

## 8. Residual risk statement

Residual risk of document egress to AI processors is **accepted as Medium** pending DPO sign-off, on the condition that: providers remain optional/fail-closed when unconfigured, human review gates promotion, and sub-processor contracts are in place before production enablement of Mistral/Gemini keys.

| Role | Name | Date | Decision |
| --- | --- | --- | --- |
| Assessor | Platform Engineering | 2026-07-11 | DPIA body complete |
| DPO / Privacy lead | _Pending_ | | Accept / reject residual risk |
| Accountable owner | _Pending_ | | Production AI key enablement |

---

## 9. Evidence pointers

| Item | Location |
| --- | --- |
| OCR service | `src/domain/services/mistral_ocr_service.py` |
| Mistral analysis | `src/domain/services/mistral_analysis_service.py` |
| Gemini review | `src/domain/services/gemini_review_service.py` |
| Import orchestration | `src/domain/services/external_audit_import_service.py` |
| Config guardrails | `src/core/config.py` (`mistral_*`, `google_gemini_api_key`) |
| Privacy contact API | `GET /api/v1/privacy/contact` |
| security.txt | `GET /.well-known/security.txt` |
| Checklist | `docs/privacy/dpia-checklist.md` |
| Governance link | `docs/governance/privacy-ocr-ai-dpia.md` |
| **S15 unsigned attestation pack** | `docs/compliance/s15-dpia-art30-attestation-pack.md` |
| Art. 30 ROPA checklist | `docs/compliance/article-30-ropa-checklist.md` |
| EA tracker (EA-03 still open) | `docs/evidence/external-attestation-tracker.md` |
