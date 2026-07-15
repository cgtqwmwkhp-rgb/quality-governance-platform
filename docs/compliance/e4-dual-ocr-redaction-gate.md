# E4 — Dual-OCR / DPIA Redaction Gate Checklist

**Document ID:** GATE-E4-OCR-REDACTION-2026-001  
**Platform:** Quality Governance Platform (QGP)  
**Lane:** Parallel LIVE Conveyor — E4  
**Status:** **OPEN** — awaiting human / ops sign-off  
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
| **This PR does not flip flags** | This document is **docs/compliance only**. It does **not** enable runtime OCR, dual-OCR paths, feature flags, secrets, or workflows. |

### Gate status

```
GATE STATUS: OPEN until human / ops sign-off
```

Closing this gate requires explicit DPO / privacy lead residual acceptance **and** an ops confirmation that pre-egress redaction / minimisation controls are in place (or formally deferred with recorded residual risk). Engineering merges of related docs PRs do **not** close this gate.

---

## Checklist — before enabling production Dual-OCR / OCR keys

### A. DPIA & residual acceptance

- [ ] Module DPIA reviewed: [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md)
- [ ] Governance operator steps followed: [`../governance/privacy-ocr-ai-dpia.md`](../governance/privacy-ocr-ai-dpia.md)
- [ ] DPO residual-risk acceptance recorded for **EA-03** in the external attestation tracker
- [ ] Accountable owner named for production AI / OCR key enablement
- [ ] Sub-processors (e.g. Mistral, Google Gemini when used) listed on DPA / SCC schedule for the target environment

### B. Redaction / minimisation (required follow-on hardening)

- [ ] Pre-egress redaction or equivalent minimisation control designed for identity / special-category content before OCR/AI upload
- [ ] Operators instructed not to upload packs with unnecessary special-category imagery (DPIA organisational measures)
- [ ] Logging confirmed not to dump document bodies or full OCR text
- [ ] Fail-closed behaviour verified when providers are unconfigured (`provider_status=not_configured` / keys unset)

### C. Explicit non-goals of *this* gate document

- [x] No dual-OCR application code changes
- [x] No production key enablement via this PR
- [x] No workflow / frontend / `src/**` changes
- [x] Gate remains **OPEN** until human / ops sign-off (not closed by merge alone)

---

## Sign-off log (human / ops)

| Role | Name | Date | Decision | Notes |
| --- | --- | --- | --- | --- |
| DPO / Privacy lead | _Pending_ | | Accept / reject residual risk | Closes EA-03 dependency for key enablement |
| Ops / Platform owner | _Pending_ | | Confirm redaction / minimisation posture | Required follow-on hardening |
| Accountable owner | _Pending_ | | Approve production OCR/AI key enablement | Only after DPO + ops rows complete |

Until all three rows are completed with an accept/approve decision, **production Dual-OCR / OCR keys stay disabled** and this gate stays **OPEN**.

---

## Evidence pointers

| Item | Location |
| --- | --- |
| OCR / AI import DPIA | `docs/compliance/dpia-ocr-ai-import.md` |
| Governance DPIA link | `docs/governance/privacy-ocr-ai-dpia.md` |
| S15 attestation pack | `docs/compliance/s15-dpia-art30-attestation-pack.md` |
| EA tracker (EA-03) | `docs/evidence/external-attestation-tracker.md` |
| Art. 30 ROPA checklist | `docs/compliance/article-30-ropa-checklist.md` |
