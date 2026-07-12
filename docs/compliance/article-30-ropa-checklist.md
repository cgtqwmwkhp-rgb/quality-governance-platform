# Article 30 — Record of Processing Activities (ROPA) Checklist

**Platform:** Quality Governance Platform (QGP)  
**Document type:** UK GDPR / EU GDPR Art. 30 documentary checklist (unsigned)  
**Version:** 1.1  
**As of:** 2026-07-12  
**Status:** Ready for privacy-lead / DPO review — **not** a completed controller ROPA  
**Related pack:** [`s15-dpia-art30-attestation-pack.md`](s15-dpia-art30-attestation-pack.md)  
**LIVE stub:** `GET /api/v1/privacy/data-processing-register` (`register_kind=article_30_stub`)

> **Honesty:** The LIVE endpoint is an auditor-facing **stub**. Controllers must maintain a full ROPA (or equivalent) under Art. 30. This checklist maps required elements to QGP sources and records gaps without inventing signed DPAs or DPO approvals.

---

## 1. Roles (who must keep records)

| Role | QGP default (multi-tenant SaaS) | Art. 30 duty |
|------|----------------------------------|--------------|
| **Controller** | Tenant organisation (customer) for their workplace / audit corpus | Full Art. 30(1) record for their processing |
| **Processor / platform operator** | Plantexpand operating QGP | Art. 30(2) processor record of categories of processing on behalf of each controller |
| **DPO** | Named by controller / operator per appointment | Contact details in ROPA when appointed |

Boxes below are for the **operator documentary pack** and the LIVE stub. Tenant controllers must complete their own ROPA entries.

---

## 2. Art. 30(1) controller elements — documentary map

| # | Required element | QGP source today | Completeness | Gap / next action |
|---|------------------|------------------|--------------|-------------------|
| A | Name and contact details of controller | Tenant org (per DPA schedule); not hardcoded in stub | Partial | Controllers supply legal entity + contact in their ROPA |
| B | DPO contact (where applicable) | Env / policy emails via `GET /api/v1/privacy/contact` (`privacy_contact`) | Partial | Confirm appointed DPO name/email — **do not invent in repo** |
| C | Purposes of processing | [`gdpr-compliance.md`](gdpr-compliance.md) §1; LIVE `activities[].name` / purpose via activity names | Ready for review | Expand stub with explicit purpose strings if auditors require verbatim Art. 30 wording |
| D | Categories of data subjects | Platform DPIA §2; incidents / OCR DPIAs | Ready for review | Add subject-category field to LIVE stub in a later code PR if needed |
| E | Categories of personal data | LIVE `activities[].data_categories`; PII inventory script evidence | Ready for review | Re-run `scripts/governance/audit_pii_fields.py` on model changes |
| F | Categories of recipients | LIVE `subprocessors`; GDPR §8 | Ready for review | Link **signed** vendor DPAs (paths only after legal files exist) |
| G | Transfers to third country / international org + safeguards | Platform DPIA §7; OCR DPIA §3.1 / §5; subprocessors `transfer_mechanism` | Partial | Confirm SCC / UK IDTA for Mistral / Gemini **before** production AI keys |
| H | Retention periods (or criteria) | [`../privacy/data-retention-policy.md`](../privacy/data-retention-policy.md); LIVE `retention` + `activities[].retention_days` | Ready for review | Matter-level legal-hold **schema** still Planned (§7a honesty) |
| I | General description of technical / organisational security measures | Platform DPIA §5; `docs/security/security-baseline.md` | Ready for review | Not a substitute for EA-02 external pen-test |

---

## 3. Art. 30(2) processor elements — operator map

| # | Required element | QGP source today | Completeness |
|---|------------------|------------------|--------------|
| P1 | Name and contact of processor | Plantexpand / QGP operator (LIVE `processor_operator`) | Documented at stub level |
| P2 | Categories of processing on behalf of each controller | LIVE `activities` + tenant isolation model | High-level stub — expand per product module as ROPA matures |
| P3 | Transfers + safeguards (where processor transfers) | Subprocessor table; OCR DPIA | Partial until AI vendor DPAs filed |
| P4 | General security measures description | DPIA §5 | Ready for review |

---

## 4. LIVE stub activity crosswalk

Aligned with `src/api/routes/privacy.py` → `_processing_activities()` after Preferred S15 stub expansion (post `#802`).

| `activity_id` | Name | Lawful basis (stub) | Retention | Notes |
|---------------|------|---------------------|-----------|-------|
| `user-accounts` | User account administration | legitimate_interest | `users_deleted` horizon post-deactivation | Controllers may also rely on contract |
| `incidents` | Incident / H&S reporting | legal_obligation | incidents policy days | May include Art. 9 special category |
| `audit-findings` | Audit findings and evidence | legitimate_interest | audit_runs policy days | Blob + PostgreSQL |
| `ocr-ai-import` | External audit OCR / AI import | legitimate_interest | Per import / evidence policy | Optional Mistral / Gemini; DPIA required |
| `auth-and-request-logs` | Authentication and API request logs | legitimate_interest | session_logs policy days | Operational security |
| `complaints` | Complaints / grievance handling | legitimate_interest | complaints policy days | Added in Preferred S15 stub expand |
| `near-misses` | Near-miss / hazard reporting | legitimate_interest | near_misses policy days | Added in Preferred S15 stub expand |
| `capa` | Corrective and preventive actions (CAPA) | legitimate_interest | audit_runs horizon (interim) | Discrete CAPA retention key still pending |
| `risk-register` | Enterprise / operational risk register | legitimate_interest | audit_runs horizon (interim) | Discrete risk retention key still pending |
| `rta` | Road traffic accident (RTA) records | legitimate_interest | incidents horizon (interim) | May include injury / special-category data |

**Still not discrete stub rows (known — expand later, not forged here):** workforce competency / UVDB supplier PII as separate activities (covered narratively in platform DPIA §2.1 and GDPR §1).

- [ ] Privacy lead accepts known stub gaps **or** schedules a follow-up code PR for remaining modules
- [ ] Controllers told stub ≠ their full Art. 30(1) record
- [ ] DPO confirms interim retention alignments for CAPA / risk / RTA before “full ROPA” claim

---

## 5. Sub-processors (recipients)

| Processor | Role | Optional | Transfer mechanism (documented) | DPA on file? |
|-----------|------|----------|----------------------------------|--------------|
| Microsoft Azure | Infrastructure | No | UK/EEA hosting | Operator responsibility — confirm Azure DPA |
| Mistral AI | OCR / extraction | Yes | SCC or UK IDTA via vendor DPA | **Pending** until production keys + legal file |
| Google Gemini | Multimodal review | Yes | SCC or UK IDTA via vendor DPA | **Pending** until production keys + legal file |

- [ ] No production AI keys without DPA path + OCR DPIA residual acceptance (EA-03 / DPIA §9)

---

## 6. Sign-off block (UNSIGNED)

| Role | Name | Date | Decision |
|------|------|------|----------|
| Assessor (engineering) | Platform Engineering | 2026-07-11 | Documentary checklist + LIVE stub aligned |
| Privacy lead / DPO | _Pending — do not invent_ | | Accept stub interim / require full ROPA expansion |
| Accountable owner | _Pending_ | | Controllers notified of Art. 30 duties |

**Engineering note:** Do not change LIVE `register_kind` away from `article_30_stub` or claim “full ROPA” until privacy lead accepts expansion and signed DPA links exist.

---

## 7. Version history

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.1 | 2026-07-12 | Platform Engineering | Crosswalk updated for expanded LIVE stub activities (complaints, near-misses, CAPA, risk, RTA) — still unsigned |
| 1.0 | 2026-07-11 | Platform Engineering | Initial Art. 30 ROPA checklist for Preferred S15 attestation pack |
