# DPIA Checklist (Path-to-10 S15)

**Platform:** Quality Governance Platform (QGP)  
**Document type:** DPIA readiness checklist (UK GDPR Art. 35 / accountability)  
**Version:** 1.0 (LIVE — OCR/AI import covered)  
**Related:** [`dpia-template.md`](dpia-template.md), [`dpia-incidents.md`](dpia-incidents.md), [`privacy-program-overview.md`](privacy-program-overview.md), [`../compliance/dpia-ocr-ai-import.md`](../compliance/dpia-ocr-ai-import.md), [`../governance/privacy-ocr-ai-dpia.md`](../governance/privacy-ocr-ai-dpia.md)

---

## Purpose

Operational checklist for confirming a DPIA is required, complete, and reviewable before go-live of a new processing activity in QGP. Use [`dpia-template.md`](dpia-template.md) for generic assessments; use the OCR/AI import DPIA for external audit document egress.

---

## Trigger checklist (is a DPIA needed?)

- [ ] New or material change to personal-data processing (modules, integrations, AI/OCR, retention)
- [ ] Systematic monitoring of individuals (e.g. location, CCTV, telematics) or large-scale employee data
- [ ] Special-category data likely in free text / images / health fields
- [ ] New cross-border transfer or new processor
- [ ] High residual risk after existing controls (tenant isolation, encryption, RBAC)
- [ ] **OCR / AI import:** enabling or changing Mistral OCR, Mistral analysis, or Gemini multimodal review on audit packs

If **any** box is checked, complete a DPIA before production enablement. For OCR/AI import use [`../compliance/dpia-ocr-ai-import.md`](../compliance/dpia-ocr-ai-import.md).

---

## Completeness checklist (before sign-off)

- [ ] Processing name, purpose, lawful basis, and data subjects documented
- [ ] Data categories and retention mapped to [`data-classification.md`](data-classification.md) / [`data-retention-policy.md`](data-retention-policy.md)
- [ ] Necessity / proportionality and alternatives considered
- [ ] Risks to data subjects identified with mitigations (technical + organisational)
- [ ] Data-subject rights paths verified (export / erasure / restriction via GDPR routes; privacy contact via `/api/v1/privacy/contact`)
- [ ] Processor / sub-processor contracts and DPA schedule updated if applicable
- [ ] Residual risk accepted by accountable owner; review date set (≤ 12 months)

### OCR / AI import completeness (when applicable)

- [ ] Sub-processors (Mistral, Google Gemini) listed on DPA schedule for the environment
- [ ] Production API keys only after residual-risk acceptance; placeholders blocked in production
- [ ] Operators briefed on minimising special-category content in uploaded packs
- [ ] Legal-hold path understood for evidence assets (`retention_policy=legal_hold`)
- [ ] EA-03 DPO sign-off tracked in `docs/evidence/external-attestation-tracker.md`

---

## Evidence pointers

| Item | Location |
| --- | --- |
| DPIA template | `docs/privacy/dpia-template.md` |
| Incidents DPIA | `docs/privacy/dpia-incidents.md` |
| **OCR / AI import DPIA** | `docs/compliance/dpia-ocr-ai-import.md` |
| Governance link | `docs/governance/privacy-ocr-ai-dpia.md` |
| Platform DPIA (compliance) | `docs/compliance/dpia-quality-governance-platform.md` |
| Privacy program overview | `docs/privacy/privacy-program-overview.md` |
| security.txt | `GET /.well-known/security.txt` |
| Privacy contact API | `GET /api/v1/privacy/contact` |

---

## Review cadence

| Cadence | Owner | Action |
| --- | --- | --- |
| Per release with privacy impact | Feature owner + DPO/privacy lead | Run trigger + completeness checklists |
| Before enabling AI provider keys | Platform + Privacy | OCR/AI import DPIA §7 organisational measures |
| Annual | Privacy lead | Re-validate open DPIAs and residual risks |
