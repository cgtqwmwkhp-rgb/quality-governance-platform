# S15 DPIA / Art. 30 Attestation Pack (UNSIGNED)

**Platform:** Quality Governance Platform (QGP)  
**Path-to-10 stage:** S15 Compliance / Privacy (Preferred target 6.5 → 9.0)  
**Document type:** Ready-for-signoff evidence pack — **not** a signed attestation  
**Version:** 1.4  
**As of:** 2026-07-12  
**Status:** `ready_for_dpo_signoff` — engineering package complete; **no DPO wet/electronic signature claimed**  
**Owner (package):** Platform Engineering / GRC  
**Owner (sign-off):** Data Protection Officer (human) — Section 9 of the platform DPIA

> **Honesty contract:** This pack deepens Article 30 and DPIA close-out evidence so a DPO can review and sign. It does **not** invent DPO names, signatures, residual-risk acceptance dates, or closed external attestations (EA-01..04). Prefer Preferred scoring credit for **unsigned readiness** only; full Preferred 9.0 for S15 still requires human EA/DPIA close-out.

---

## 1. Purpose

Single index a DPO / auditor can walk without hunting the repo:

1. Confirm DPIA bodies are complete and residual risks are reviewable.
2. Confirm the Art. 30-style processing register (LIVE stub + documentary ROPA checklist) is coherent.
3. Confirm what is still **open** on EA-01..04 — none are closed by this pack.
4. Complete Section 9 of the platform DPIA (and EA-03 deliverable) when ready.

---

## 2. Pack inventory (SSOT pointers)

| # | Artifact | Path / endpoint | Role in sign-off |
|---|----------|-----------------|------------------|
| 1 | Platform DPIA (Art. 35) | [`dpia-quality-governance-platform.md`](dpia-quality-governance-platform.md) | Primary DPIA; §9 blank for DPO; §10 readiness |
| 2 | OCR / AI import DPIA | [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md) | Companion DPIA; residual Medium pending DPO |
| 3 | Incidents DPIA | [`../privacy/dpia-incidents.md`](../privacy/dpia-incidents.md) | Module DPIA (DPIA-001) |
| 4 | DPIA operational checklist | [`../privacy/dpia-checklist.md`](../privacy/dpia-checklist.md) | Trigger + completeness gates |
| 5 | Art. 30 ROPA documentary checklist | [`article-30-ropa-checklist.md`](article-30-ropa-checklist.md) | Field-by-field Art. 30 readiness (unsigned) |
| 6 | GDPR compliance + LIVE endpoints | [`gdpr-compliance.md`](gdpr-compliance.md) §8 | Inventory + machine-readable disclosure map |
| 7 | Retention / soft-delete / legal-hold SSOT | [`../privacy/data-retention-policy.md`](../privacy/data-retention-policy.md) §7a–§7b | Retention truth; schema hold gaps stated honestly |
| 8 | Privacy program overview | [`../privacy/privacy-program-overview.md`](../privacy/privacy-program-overview.md) | Program map + DPIA register |
| 9 | External attestation tracker | [`../evidence/external-attestation-tracker.md`](../evidence/external-attestation-tracker.md) | EA-01..04 status SSOT (still open) |
| 10 | LIVE privacy contact | `GET /api/v1/privacy/contact` | `dpia.status=pending_dpo_signoff`, `dpia.attestation_pack`, subprocessors, retention |
| 11 | LIVE Art. 30 stub register | `GET /api/v1/privacy/data-processing-register` | `register_kind=article_30_stub` — purpose / subject categories + `technical_organisational_measures` + `international_transfers`; **not** full ROPA |
| 12 | security.txt | `GET /.well-known/security.txt` | Public security / privacy contact path |

---

## 3. External attestation honesty (EA-01..04)

Mirror of [`../evidence/external-attestation-tracker.md`](../evidence/external-attestation-tracker.md) as of 2026-07-11. **This pack does not change EA status.**

| ID | Dimension | Attestation | Honest status | Blocks Preferred 9.0? |
|----|-----------|-------------|---------------|------------------------|
| **EA-01** | D03 Accessibility | WCAG 2.1 AA external audit + VPAT | 🔴 **Not started** | Yes — external assessor required |
| **EA-02** | D06 Security | External penetration test (CREST/equiv.) | 🟡 **Scheduled** (not executed / not remediating) | Yes — report + Critical/High close-out required |
| **EA-03** | D07 Privacy | DPO sign-off on DPIAs | 🟡 **In progress** — bodies ready; **§9 unsigned** | Yes — this pack prepares EA-03; does **not** close it |
| **EA-04** | D08 Compliance | ISO auditor validation of evidence tool | 🔴 **Not started** | Yes — independent auditor required |

### What engineering may claim after this pack lands

| Claim | Allowed? |
|-------|----------|
| DPIA technical sections complete; ready for DPO review | Yes |
| Art. 30 stub LIVE + documentary ROPA checklist ready for expansion / sign-off | Yes |
| `dpia.status=pending_dpo_signoff` | Yes (must remain until §9 signed) |
| EA-01 / EA-02 / EA-04 closed | **No** |
| EA-03 closed / DPIA “Approved” / named DPO signature present | **No** |
| Full controller ROPA complete | **No** — stub + checklist only |

---

## 4. DPIA close-out checklist (UNSIGNED — for DPO)

Copy outcomes into `docs/evidence/dpo-signoff-YYYY-Q?.md` when the DPO actually signs. Until then, leave boxes unchecked.

### 4.1 Documents in scope

- [ ] Platform DPIA [`dpia-quality-governance-platform.md`](dpia-quality-governance-platform.md) §§1–8 reviewed against live processing
- [ ] OCR/AI import DPIA [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md) residual-risk statement reviewed
- [ ] Incidents DPIA [`../privacy/dpia-incidents.md`](../privacy/dpia-incidents.md) still current or scheduled for re-review
- [ ] Soft-delete-first + matter-level legal-hold honesty accepted ([`../privacy/data-retention-policy.md`](../privacy/data-retention-policy.md) §7a — schema flags may still be Planned)

### 4.2 Risks and conditions

- [ ] Special-category / RIDDOR flows accepted or conditioned
- [ ] OCR/AI Medium residual risk accepted, rejected, or conditioned (keys remain off until accepted)
- [ ] Sub-processor list reviewed (Azure required; Mistral / Gemini optional when keys set)
- [ ] No high residual risk requiring ICO Art. 36 prior consultation (or consultation initiated)

### 4.3 Machine-readable consistency

- [ ] `GET /api/v1/privacy/contact` → `dpia.status` is `pending_dpo_signoff` **before** sign-off
- [ ] After sign-off only: engineering updates `_DPIA_STATUS` / docs Status **and** EA-03 tracker — **never** before §9 is completed by the DPO
- [ ] `GET /api/v1/privacy/data-processing-register` activities align with this pack’s Art. 30 checklist

### 4.4 Section 9 completion (DPO only)

| Field | Value |
|-------|-------|
| DPO Name | _[To be completed by DPO — do not invent]_ |
| DPO Review Date | _[To be completed by DPO]_ |
| DPO Decision | Approved / Approved with conditions / Rejected |
| Conditions (if any) | _[To be completed by DPO]_ |
| DPO Signature | _[Wet or electronic — do not forge]_ |
| EA-03 deliverable path | `docs/evidence/dpo-signoff-YYYY-Q?.md` (create on sign-off) |

---

## 5. Art. 30 close-out checklist (UNSIGNED)

Full field matrix: [`article-30-ropa-checklist.md`](article-30-ropa-checklist.md).

Engineering readiness summary:

| Art. 30 element | Documentary / LIVE state | Sign-off blocker? |
|-----------------|--------------------------|-------------------|
| Controller / processor identity | Documented (tenant controller; Plantexpand operator); LIVE `roles_and_contacts` | DPO confirms roles per DPA — DPO identity not invented |
| Purposes + lawful bases | Inventory in GDPR §1 + LIVE `activities[].purpose` / `lawful_basis` | DPO confirms per tenant workflow |
| Data subject / data categories | DPIA + LIVE `data_subject_categories` / `data_categories` | Stub taxonomy only — not full controller ROPA |
| Recipients / subprocessors | LIVE `subprocessors` + DPIA OCR companion | Signed vendor DPAs still required where AI enabled |
| International transfers | UK South primary; LIVE `international_transfers` + AI vendors vendor-managed | Confirm SCC/UK IDTA before production AI keys — **no signed DPAs invented** |
| Retention | Retention policy §7 + LIVE `retention` block | Legal-hold schema gap acknowledged |
| Security measures (general) | DPIA §5 + security baseline + LIVE `technical_organisational_measures` | Not a substitute for EA-02 pen-test |

- [ ] DPO / privacy lead accepts stub as interim disclosure **or** commissions full ROPA expansion
- [ ] Signed DPA links recorded for each active sub-processor (not invented here)

---

## 6. Scoring note (Path-to-10 Preferred)

| Lane | Score movement this pack supports |
|------|-----------------------------------|
| S15 documentation / accountability | Toward Preferred via **unsigned** ready-for-signoff depth |
| S15 full Preferred 9.0 | Still gated on **human** EA-01..04 + signed DPIA (EA-03) |

Do not mark S15 Preferred complete solely because this pack exists.

---

## 7. Version history

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.5 | 2026-07-12 | Platform Engineering | LIVE stub `roles_and_contacts` (Art. 30 gaps A/B/P1) — still **unsigned** / DPO identity not invented / EA open |
| 1.4 | 2026-07-12 | Platform Engineering | LIVE stub `international_transfers` (Art. 30 gap G) — still **unsigned** / AI DPAs not invented / EA open |
| 1.3 | 2026-07-12 | Platform Engineering | LIVE stub `technical_organisational_measures` (Art. 30 gap I) — still **unsigned** / EA open |
| 1.2 | 2026-07-12 | Platform Engineering | LIVE stub `purpose` + `data_subject_categories` (Art. 30 gaps C/D) — still **unsigned** / EA open |
| 1.1 | 2026-07-12 | Platform Engineering | LIVE stub activity expand + machine-readable attestation_pack pointers — still **unsigned** / EA open |
| 1.0 | 2026-07-11 | Platform Engineering | Initial unsigned DPIA / Art. 30 attestation pack for Preferred S15 |
