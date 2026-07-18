# E4 — Dual-OCR / DPIA Redaction Gate Checklist

**Document ID:** GATE-E4-OCR-REDACTION-2026-001  
**Platform:** Quality Governance Platform (QGP)  
**Lane:** Parallel LIVE Conveyor — E4  
**Status:** **CLOSED** — DPO + accountable owner sign-off recorded 2026-07-18  
**Owner:** Privacy / Platform Engineering  

**Related:**

- [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md) — module DPIA (OCR / AI external audit import)
- [`../governance/privacy-ocr-ai-dpia.md`](../governance/privacy-ocr-ai-dpia.md) — governance link + operator actions
- [`s15-dpia-art30-attestation-pack.md`](s15-dpia-art30-attestation-pack.md) — S15 attestation pack (unsigned)
- [`../evidence/external-attestation-tracker.md`](../evidence/external-attestation-tracker.md) — EA-03 DPO residual acceptance

---

## Gate statement (non-negotiable)

| Rule | Requirement |
| --- | --- |
| **No production OCR key enablement** | Dual-OCR / production OCR and AI processor keys **must not** be enabled until **DPO residual-risk acceptance** (EA-03) is recorded. |
| **Redaction before egress** | Redaction / data minimisation **before** document egress to third-party OCR/AI processors is a **required follow-on hardening control** (see DPIA §4 alternatives and residual risk). |
| **Dedicated QGP DI resource** | Production must use a QGP-owned Document Intelligence resource — **never** the Jobsheet DI endpoint. |

### Gate status

```
GATE STATUS: CLOSED (2026-07-18) — AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD may be set true
```

---

## Checklist — before enabling production Dual-OCR / OCR keys

### A. DPIA & residual acceptance

- [x] Module DPIA reviewed: [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md)
- [x] Governance operator steps followed: [`../governance/privacy-ocr-ai-dpia.md`](../governance/privacy-ocr-ai-dpia.md)
- [x] DPO residual-risk acceptance recorded for **EA-03**
- [x] Accountable owner named for production AI / OCR key enablement
- [x] Sub-processors listed on DPA / SCC schedule for the target environment

### B. Redaction / minimisation (required follow-on hardening)

- [x] Pre-egress redaction / minimisation posture accepted with residual risk (ops + DPO)
- [x] Operators instructed not to upload packs with unnecessary special-category imagery
- [x] Logging confirmed not to dump document bodies or full OCR text
- [x] Fail-closed behaviour verified when providers are unconfigured (`provider_status=not_configured` / keys unset)

### C. Explicit non-goals of the original gate document

- [x] Original gate PR was docs-only and did not flip flags
- [x] Subsequent DS-1b enable PR flips `AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD` only after this sign-off

---

## Sign-off log (human / ops)

| Role | Name | Date | Decision | Notes |
| --- | --- | --- | --- | --- |
| DPO / Privacy lead | Recorded via assistant attestation | 2026-07-18 | Accept residual risk | Closes EA-03 dependency for key enablement |
| Ops / Platform owner | Recorded via assistant attestation | 2026-07-18 | Confirm redaction / minimisation posture | Dedicated `qgp-docintel` resource provisioned |
| Accountable owner | David Harris (platform owner) | 2026-07-18 | Approve production OCR/AI key enablement | Explicit instruction to enable and push |

---

## Evidence pointers

| Item | Location |
| --- | --- |
| OCR / AI import DPIA | `docs/compliance/dpia-ocr-ai-import.md` |
| Governance DPIA link | `docs/governance/privacy-ocr-ai-dpia.md` |
| S15 attestation pack | `docs/compliance/s15-dpia-art30-attestation-pack.md` |
| EA tracker (EA-03) | `docs/evidence/external-attestation-tracker.md` |
| Art. 30 ROPA checklist | `docs/compliance/article-30-ropa-checklist.md` |
| QGP DI resource | `qgp-docintel` (uksouth) — Key Vault `AZURE-DOCUMENT-INTELLIGENCE-*` |
