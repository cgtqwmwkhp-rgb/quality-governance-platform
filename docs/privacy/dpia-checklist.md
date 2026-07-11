# DPIA Checklist Stub (Path-to-10 S15)

**Platform:** Quality Governance Platform (QGP)  
**Document type:** DPIA readiness checklist (UK GDPR Art. 35 / accountability)  
**Version:** 0.1 (stub — LIVE documentation)  
**Related:** [`dpia-template.md`](dpia-template.md), [`dpia-incidents.md`](dpia-incidents.md), [`privacy-program-overview.md`](privacy-program-overview.md)

---

## Purpose

Operational checklist for confirming a DPIA is required, complete, and reviewable before go-live of a new processing activity in QGP. This stub does **not** replace a full DPIA; use [`dpia-template.md`](dpia-template.md) for the assessment body.

---

## Trigger checklist (is a DPIA needed?)

- [ ] New or material change to personal-data processing (modules, integrations, AI/OCR, retention)
- [ ] Systematic monitoring of individuals (e.g. location, CCTV, telematics) or large-scale employee data
- [ ] Special-category data likely in free text / images / health fields
- [ ] New cross-border transfer or new processor
- [ ] High residual risk after existing controls (tenant isolation, encryption, RBAC)

If **any** box is checked, complete a DPIA using the template before production enablement.

---

## Completeness checklist (before sign-off)

- [ ] Processing name, purpose, lawful basis, and data subjects documented
- [ ] Data categories and retention mapped to [`data-classification.md`](data-classification.md) / [`data-retention-policy.md`](data-retention-policy.md)
- [ ] Necessity / proportionality and alternatives considered
- [ ] Risks to data subjects identified with mitigations (technical + organisational)
- [ ] Data-subject rights paths verified (export / erasure / restriction via GDPR routes)
- [ ] Processor / sub-processor contracts and DPA schedule updated if applicable
- [ ] Residual risk accepted by accountable owner; review date set (≤ 12 months)

---

## Evidence pointers

| Item | Location |
| --- | --- |
| DPIA template | `docs/privacy/dpia-template.md` |
| Incidents DPIA | `docs/privacy/dpia-incidents.md` |
| Platform DPIA (compliance) | `docs/compliance/dpia-quality-governance-platform.md` |
| Privacy program overview | `docs/privacy/privacy-program-overview.md` |

---

## Review cadence

| Cadence | Owner | Action |
| --- | --- | --- |
| Per release with privacy impact | Feature owner + DPO/privacy lead | Run trigger + completeness checklists |
| Annual | Privacy lead | Re-validate open DPIAs and residual risks |

**Stub status:** LIVE documentation artifact for Path-to-10 S15. Expand with module-specific rows as DPIAs are completed.
