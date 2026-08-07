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
| DPO / Privacy lead | **David Harris** | 2026-07-28 | Accept residual risk | Named human acceptance of EA-03, given explicitly on 28/07. **Recorded under today's date, not backdated to 18/07** — see note below. |
| DPO / Privacy lead | **David Harris** | 2026-08-06 | Accept residual risk — DPIA v2.0 expanded processors | Accepts HIGH residual risk for Anthropic, OpenAI, Voyage AI, Pinecone (and continues v1.0 acceptance). §7 organisational measures remain open follow-ons. |
| Ops / Platform owner | Recorded via assistant attestation | 2026-07-18 | Confirm redaction / minimisation posture | Dedicated `qgp-docintel` resource provisioned. **Still unsigned — see note below.** |
| Accountable owner | David Harris (platform owner) | 2026-07-18 | Approve production OCR/AI key enablement | Explicit instruction to enable and push |

### Note on the EA-03 acceptance recorded above (added 2026-07-28)

Three things about this row need to be legible to anyone auditing it later, because
recording it silently would defeat the purpose of the gate.

**1. It is deliberately dated 28 July, not 18 July.** The row previously read
"Recorded via assistant attestation". No human DPO acceptance existed on 18 July, so
production OCR/AI key enablement went ahead against an attestation that had not been
given. Dating this signature 18/07 would have made the record internally consistent by
falsifying it. The acceptance is therefore recorded on the date it was actually given
and **retrospectively covers the enablement of 18 July**, which ran for ten days without
it. The gap is the finding; concealing it would have been the more serious act.

**2. The same person now signs as both DPO / Privacy lead and Accountable owner.**
That is a concentration of roles, and the control is weaker for it: the person accepting
the residual privacy risk is the person who asked for the feature to be enabled. On a
platform this size that may be unavoidable and it is the controller's call, but it should
be visible on the record rather than inferred by whoever reads it next.

**3. The Ops / Platform owner row is still an assistant attestation.** It was not covered
by the instruction that produced the DPO signature, so it has deliberately been left as
it was rather than assumed to be the same person. It asserts that the redaction and
minimisation posture was confirmed — and note that pre-egress redaction is still a
*planned* control, not an implemented one, which makes this the row most in need of a
human name.

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

---

## Post-closure note (2026-07-28) — disclosure follow-up

This gate is not reopened. Two facts found while reconciling the published Article 30 register
against production are recorded here because they bear on item **A**:

1. Azure AI Document Intelligence was **enabled in production but named in no DPIA and in no
   published sub-processor register** until 2026-07-28. It now appears in
   [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md) §2.0a and in
   `GET /api/v1/privacy/data-processing-register`.
2. Item A's "Sub-processors listed on DPA / SCC schedule for the target environment" cannot be
   evidenced from this repository for any AI processor: no vendor DPA, SCC or UK IDTA artifact is
   filed here. The `qgp-docintel` resource being in `uksouth` is the only region fact this
   repository establishes for an AI processor, and it is what the register now cites.

The register's UK South claim for this processor rests on the resource recorded above. If the
deployed `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` ever points at a resource in another region, the
register becomes inaccurate — that value is not verifiable from the repository.
