# GDPR Compliance Documentation (D07)

**Owner**: Platform Engineering / Data Protection
**Last Updated**: 2026-07-11
**Review Cycle**: Annually and on material changes

---

## 1. Data Processing Inventory

| Data Category | Examples | Lawful Basis | Retention | Storage |
|---------------|----------|-------------|-----------|---------|
| User accounts | Email, name, role | Legitimate interest (platform access) | Account lifetime + 90 days | PostgreSQL |
| Incident reports | Description, location, severity | Legal obligation (H&S reporting) | 7 years | PostgreSQL |
| Audit findings | Finding text, evidence references | Legitimate interest (quality governance) | 7 years | PostgreSQL |
| CAPA actions | Action description, assignee | Legitimate interest (corrective action tracking) | 7 years | PostgreSQL |
| Risk register | Risk description, scores | Legitimate interest (enterprise risk management) | 7 years | PostgreSQL |
| Complaints | Complainant details, narrative | Legal obligation (regulatory compliance) | 7 years | PostgreSQL |
| Evidence assets | PDF documents, images | Legitimate interest (audit evidence) | Per retention policy | Azure Blob Storage |
| Authentication logs | Login times, IP addresses | Legitimate interest (security monitoring) | 90 days | Structured logs |
| Request logs | API paths, tenant_id, user_id | Legitimate interest (operational monitoring) | 90 days | Azure Log Analytics |

---

## 2. Data Subject Rights

| Right | Implementation | Status |
|-------|---------------|--------|
| Right of access (Art. 15) | User profile page shows personal data; admin export available | Implemented |
| Right to rectification (Art. 16) | Profile editing; admin can update user records | Implemented |
| Right to erasure (Art. 17) | Soft-delete of user account; anonymization of linked records | Partial — hard delete not yet automated |
| Right to restriction (Art. 18) | Account deactivation prevents login and data processing | Implemented |
| Right to portability (Art. 20) | JSON export of user-owned data via API | Planned |
| Right to object (Art. 21) | Contact platform admin to object to processing | Manual process |

---

## 3. Data Protection Impact Assessment (DPIA) Summary

| Factor | Assessment |
|--------|------------|
| **Nature of processing** | Multi-tenant SaaS platform processing workplace safety, quality, and compliance data |
| **Scope** | Organizational users (employees) within tenant organizations |
| **Context** | Professional/employment context; no special category data unless disclosed in free-text fields |
| **Purpose** | Quality governance, incident management, audit tracking, regulatory compliance |
| **Risk to individuals** | Low-Medium — primarily professional data; free-text fields could contain sensitive details |
| **Mitigations** | Role-based access, tenant isolation, encryption at rest and in transit, audit logging, retention limits |

### DPIA Conclusion

The processing is necessary for legitimate business purposes. Risks are mitigated through technical and organizational measures. No high residual risk requiring supervisory authority consultation.

---

## 4. Technical Measures

| Measure | Implementation | Evidence |
|---------|---------------|----------|
| Encryption at rest | Azure-managed encryption for PostgreSQL and Blob Storage | Azure platform default |
| Encryption in transit | TLS 1.2+ enforced on all endpoints | `staticwebapp.config.json`, App Service HTTPS enforcement |
| Access control | JWT-based authentication, role-based authorization | `src/api/middleware/auth.py` |
| Tenant isolation | Row-level `tenant_id` filtering on all queries | `src/api/dependencies.py` |
| Audit logging | Structured request logs with user_id and tenant_id | `src/infrastructure/middleware/request_logger.py` |
| Password security | bcrypt hashing with salt | `src/infrastructure/auth/` |
| Secret management | Azure Key Vault for production secrets | `scripts/infra/` |

---

## 5. Data Retention Schedule

| Data Type | Active Retention | Archive | Deletion |
|-----------|-----------------|---------|----------|
| User accounts | Account lifetime | 90 days post-deactivation | Anonymized |
| Incident records | 7 years from creation | N/A | Soft-deleted |
| Audit records | 7 years from audit date | N/A | Soft-deleted |
| Evidence assets | Per audit record retention | Move to Cool tier after 90 days | Delete with parent record |
| Authentication logs | 90 days | N/A | Auto-purged |
| Request logs | 90 days | N/A | Auto-purged by Azure Log Analytics |

See also: [`docs/evidence/retention-automation-evidence.md`](../evidence/retention-automation-evidence.md)

---

## 6. Breach Notification Process

| Step | Timeframe | Action |
|------|-----------|--------|
| 1. Detection | Immediate | Security incident logged; on-call notified |
| 2. Assessment | Within 4 hours | Determine if personal data affected; assess severity |
| 3. Containment | Within 8 hours | Isolate affected systems; preserve forensic evidence |
| 4. ICO notification | Within 72 hours | Notify Information Commissioner's Office if threshold met |
| 5. Data subject notification | Without undue delay | Notify affected individuals if high risk to rights/freedoms |
| 6. Post-incident review | Within 14 days | Root cause analysis; preventive measures documented |

---

## 7. International Transfers

### 7.1 Platform hosting — UK/EEA, but not UK-only

**Corrected 2026-07-28.** This section previously stated that the platform is "hosted entirely within
Azure UK South region". That was false. Production is split across two Azure regions:

| Purpose | Region | Resource (production) |
|---------|--------|------------------------|
| Application processing — API, Celery worker, Celery beat | **West Europe** (Netherlands) | `app-qgp-prod`, `app-qgp-prod-worker`, `app-qgp-prod-beat` on `plan-qgp-staging-weu` |
| **Uploaded documents / evidence at rest** | **West Europe** | production blob storage account (container `evidence-assets`) |
| Secrets | **West Europe** | `kv-qgp-prod` |
| Telemetry | **West Europe** | `appi-qgp-staging` (Application Insights) |
| Frontend | **West Europe** | `qgp-frontend` |
| Primary database (personal data at rest) | UK South | `psql-qgp-prod` (PostgreSQL 16) |
| Cache | UK South | `redis-qgp-prod` |
| OCR (Azure AI Document Intelligence) | UK South | `qgp-docintel` |

**Legal characterisation — do not overstate this.** The Netherlands is in the EEA. There is **no
third-country transfer** and **no unlawfulness** of the kind that applies to the US-hosted AI
processors in §8. **No SCC or UK IDTA is engaged by this split**, and none should be attached to it.

**What is actually wrong** is the accuracy of the Article 30 record: it stated UK South for hosting,
blob storage and application processing when those are in West Europe. An Art. 30 record must state
where processing occurs. The practical exposure is that **any customer-facing statement, tender
response or DPA saying the platform is "hosted in the UK" is false for application processing and
for uploaded document storage at rest** — a factual misstatement to data subjects and customers.
Statements should say UK/EEA, or state the split.

**Status:** known infrastructure defect, scheduled for remediation by IT after UAT. Target is
co-location in **UK South**; the blob storage account requires a copy, so it is treated as its own
change. Sources: [`../adr/ADR-0019-production-hosting-isolation-and-region.md`](../adr/ADR-0019-production-hosting-isolation-and-region.md)
(documents the same split, status Proposed 2026-07-25) and
`docs/run026-IT-HANDOVER-infrastructure-package.md` (Item 3). Verified 2026-07-28 by Azure CLI
resource enumeration of the live subscription by the accountable owner.

Machine-readable equivalent: `GET /api/v1/privacy/data-processing-register` →
`international_transfers.hosting_regions_by_purpose` and `international_transfers.azure_region_defect`.

Two regions are not separately verified and are published as unknown: the Entra ID directory region
(a directory service this platform does not region-pin) and the Log Analytics workspace region.

### 7.2 AI sub-processor transfers

Transfers to the AI processors in §8 are a separate and more serious question: their regions and
transfer safeguards are **not established**, and no vendor DPA, SCC or UK IDTA artifact exists in
this repository. See [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md) §2.0a. If future requirements
necessitate a confirmed third-country transfer, appropriate safeguards (SCCs, UK IDTA, or an
adequacy decision) must be in place before the transfer — for the AI processors already live, that
is remediation rather than a precondition.

---

## 8. Machine-readable compliance LIVE (Path-to-10 S15)

| Endpoint | Surfaces |
|----------|----------|
| `GET /api/v1/privacy/contact` | Privacy/security contacts, `retention`, `subprocessors`, `dpia.status`, register pointer |
| `GET /api/v1/privacy/data-processing-register` | Article 30-style **stub** register (activities + subprocessors + DPIA status + `roles_and_contacts` + `technical_organisational_measures` + `international_transfers`) |

`dpia.status` is `signed` as of 2026-07-12 (EA-03 / DPIA §9 closed —
[`dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md`](../evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md)).
The processing register is intentionally a stub (`register_kind=article_30_stub`) — activity rows
include complaints, near-misses, CAPA, risk register, and RTA plus additive `purpose` /
`data_subject_categories` fields for Art. 30(1)(b)/(c) readability, a register-level
`roles_and_contacts` block for Art. 30 A/B/P1 pointers (**DPO identity not invented**;
`dpo.contact_email` stays `null` until appointed), a
`technical_organisational_measures` block for Art. 30(1)(g) (general TOMs; **not** EA-02),
and `international_transfers` for Art. 30(1)(e) (West Europe application processing and
documents at rest, UK South database — both UK/EEA, see §7.1; AI vendor
transfers pending SCC/UK IDTA — **no signed vendor DPAs invented**).
Signed DPA links + EA-01/02/04 are still required before treating it as a full controller ROPA.
LIVE `dpia.attestation_pack` / `dpia.article_30_checklist` point at the attestation pack.

Documentary Art. 30 field map: [`article-30-ropa-checklist.md`](article-30-ropa-checklist.md).  
DPIA + Art. 30 attestation pack: [`s15-dpia-art30-attestation-pack.md`](s15-dpia-art30-attestation-pack.md).

Sub-processors disclosed (also on `/privacy/contact`):

| Processor | Role | Optional | Retention posture | Region / transfer mechanism |
|-----------|------|----------|-------------------|------------------------------|
| Microsoft Azure | Infrastructure (hosting, DB, blob, Entra ID, logs, Key Vault) | No | Hosts platform data | **Split, verified 2026-07-28:** app processing, uploaded documents at rest, secrets and telemetry in **West Europe**; database, cache and registry in **UK South**. UK/EEA hosting, no third-country transfer — see §7.1 |
| Azure AI Document Intelligence | Dual-OCR / library OCR failover (enabled in production, E4 gate closed) | Yes | Transient | UK South per E4 gate resource evidence (`qgp-docintel`, uksouth) |
| Mistral AI | OCR / structured extraction | Yes (live in production) | Transient | **Unknown** |
| Google Gemini | Multimodal review | Yes (live in production) | Transient | **Unknown** |
| Anthropic | Document + case analysis (preferred shared AI client) | Yes (live in production) | Transient | **Unknown** |
| OpenAI | Fallback LLM on shared AI client paths | Yes (live in production) | Transient | **Unknown** |
| Voyage AI | Chunk and query embeddings | Yes (live in production) | Transient | **Unknown** |
| **Pinecone** | **Vector index — stores embeddings and verbatim chunk previews** | Yes (live in production) | **Retains content until deleted by QGP** | **Unknown** |
| Genspark.ai | Legacy shared-AI-client fallback | Yes | Transient | **Unknown**; activation not confirmed |
| Perplexity | Horizon scanning / audit-builder research | Yes | Transient | **Unknown**; activation not confirmed |

`Unknown` is literal, not a placeholder for "probably fine": no client in the codebase pins a
processing region and no vendor DPA / SCC / UK IDTA artifact exists in this repository for the
third-party AI processors. The controller must establish each vendor's location and safeguard.
Azure AI Document Intelligence is the one AI processor with a sourced region claim (E4 gate). Detail, data flows and
what each processor actually receives: [`dpia-ocr-ai-import.md`](dpia-ocr-ai-import.md) §2.0a and §3.

The provider ↔ credential ↔ disclosure join is enforced in code
([`src/core/ai_provider_disclosure.py`](../../src/core/ai_provider_disclosure.py)): adding a provider
credential to `Settings` without a register entry fails
`tests/unit/test_ai_provider_disclosure.py`.

---

## 9. External attestation honesty (EA-01..04)

Preferred S15 (target 9.0) still requires human external attestations. Documentation and LIVE
stubs do **not** close EA items. Tracker SSOT:
[`docs/evidence/external-attestation-tracker.md`](../evidence/external-attestation-tracker.md).

| ID | Type | Honest status (2026-07-11) |
|----|------|----------------------------|
| EA-01 | WCAG 2.1 AA external audit | 🔴 Not started |
| EA-02 | External penetration test | 🟡 Scheduled (not completed) |
| EA-03 | DPO sign-off on DPIAs | 🟡 In progress — pack ready, §9 **unsigned** |
| EA-04 | ISO auditor validation of evidence tool | 🔴 Not started |

---

## Related Documents

- [`docs/compliance/s15-dpia-art30-attestation-pack.md`](s15-dpia-art30-attestation-pack.md) — unsigned ready-for-signoff pack
- [`docs/compliance/article-30-ropa-checklist.md`](article-30-ropa-checklist.md) — Art. 30 documentary checklist
- [`docs/evidence/retention-automation-evidence.md`](../evidence/retention-automation-evidence.md) — retention policy evidence
- [`docs/privacy/data-retention-policy.md`](../privacy/data-retention-policy.md) — retention / soft-delete / legal-hold SSOT (§7a–§7b)
- `GET /api/v1/privacy/contact` → `retention`, `subprocessors`, `dpia.status`
- `GET /api/v1/privacy/data-processing-register` — Art. 30 stub register
- [`docs/security/security-baseline.md`](../security/security-baseline.md) — security controls
- [`docs/adr/ADR-0009-csrf-not-required.md`](../adr/ADR-0009-csrf-not-required.md) — CSRF decision
