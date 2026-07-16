# Data Retention Policy — QGP

**Platform:** Quality Governance Platform (QGP)  
**Version:** 1.0  
**Related:** `docs/privacy/dpia-template.md`, `src/domain/models/audit_log.py`, `src/infrastructure/tasks/celery_app.py`

---

## 1. Purpose

This policy defines how long categories of records are retained in QGP, the legal bases for retention, how they are disposed of, and how automated retention is tied to the data model (including `AuditLogEntry.retention_days`).

---

## 2. Retention schedule

| Entity / record class | Retention period | Legal basis (typical) | Disposal method |
| --- | --- | --- | --- |
| **Incidents** | 7 years | Legitimate interest (safety); legal / liability preservation | Soft-delete or archive then purge per tenant rules; attachments removed from primary storage after archival |
| **Audit log entries** (`AuditLogEntry`) | 7 years (default **2555 days** per `retention_days`) | Legal obligation / legitimate interest (accountability, disputes) | Delete expired rows per retention job; retain verification/export metadata as required |
| **RTAs** | 6 years | Road traffic / insurance / regulatory (jurisdiction-specific) | Purge or archive to cold storage after active period |
| **Complaints** | 3 years | Contract / consumer / employment obligations (varies) | Close, archive, then secure deletion |
| **Employee / user accounts** | Life of employment + statutory window | Contract / legal obligation | Deactivation; GDPR erasure / pseudonymisation via GDPR service when applicable |
| **Vehicle checks / driver profiles** | Aligned to fleet policy (often 6–7 years for safety evidence) | Legitimate interest / legal obligation | Anonymise driver links where possible; purge obsolete checks |
| **Witness statements / photos** | Follows parent incident / case | As per incident retention | Delete with parent record or redact in place |
| **Tokens / session artefacts** | Operational minimum (hours–days) | Security | Automated cleanup (e.g. token blacklist housekeeping) |

> **Legal basis** column is indicative — each controller must confirm against legal advice and the ROPA.

---

## 3. `retention_days` on `AuditLogEntry`

The `AuditLogEntry` model includes:

- **`retention_days`**: integer, **default `2555`** (~7 years from creation, calendar interpretation per job logic).
- Purpose: support **per-entry** or per-tenant policy overrides without schema churn.

**Semantics (policy intent):**

1. Each audit row carries its own retention horizon: `expiry ≈ timestamp + retention_days` (UTC calendar day boundary may be applied by the job).
2. Purge jobs select entries where the computed expiry is **before** “today” and delete or archive them according to tenant configuration.
3. **Hash chain:** Deleting entries from the middle of a chain can break sequence integrity; production implementations should use **archival** (move to cold store) or **tenant-scoped chain rebuild** strategies rather than silent deletion unless approved by security / compliance.

**Code references:**

- Model default: `src/domain/models/audit_log.py` (`retention_days` default `2555`).
- Scheduled task hook: `src/infrastructure/tasks/celery_app.py` — beat entry `run-data-retention` → `src.infrastructure.tasks.cleanup_tasks.run_data_retention`.

---

## 4. Automated purge

| Component | Behaviour |
| --- | --- |
| **Scheduler** | Celery Beat runs `run_data_retention` **daily at 02:00 UTC** (see `celery_app.conf.beat_schedule`). |
| **Task** | `run_data_retention` in `src/infrastructure/tasks/cleanup_tasks.py` — orchestrates retention passes (extend to query `AuditLogEntry` and other entities by `retention_days` / policy tables). |
| **Operational requirement** | Workers on the **`cleanup`** queue must be running in environments where retention is mandatory. |

**Gap / roadmap:** The retention task should explicitly implement purge queries (with batching, metrics, and dry-run mode) and emit structured logs for disposal verification.

---

## 5. Archive strategy (cold storage)

For records **beyond active operational retention** but still within legal hold or infrequent access:

1. **Export** structured snapshots (JSON/CSV) and register them in `AuditLogExport` (includes `file_hash` for integrity).
2. Move blobs to **Azure Blob** archive / cool tier (or organisational WORM / backup vault).
3. Redact or tokenise direct identifiers in archived bundles where proportionate.
4. Retain **index metadata** (tenant, date range, record counts) in QGP or CMDB for retrieval audits.

---

## 6. Disposal verification

| Control | Description |
| --- | --- |
| **Structured logging** | Retention jobs log tenant ID, entity type, count deleted/archived, job ID, correlation / `request_id`. |
| **Audit trail** | High-risk disposal actions should generate `AuditLogEntry` rows (action e.g. `retention_purge`) **before** destructive steps where feasible. |
| **Export hash** | Pre-disposal exports recorded in `audit_log_exports.file_hash` provide evidence of what left the system. |
| **Monitoring** | Alert on retention job failures or zero-run streaks; quarterly sample verification of row counts vs policy. |

---

## 7a. Legal hold & soft-delete SSOT (Path-to-10 S15)

**Status:** LIVE documentation — soft-delete-first policy is coded; a matter-level hold register is now a first-class schema. Retention-worker enforcement remains a separate, open implementation step.

| Layer | Source of truth | Behaviour today |
| --- | --- | --- |
| **Policy defaults** | `src/core/retention_config.py` (`RetentionPolicy.soft_delete_first=True`) | Entity retention horizons (incidents/complaints/near_misses/audit_runs/audit_logs) prefer soft-delete before hard purge |
| **Scheduler** | Celery Beat `run-data-retention` → `cleanup_tasks.run_data_retention` | Daily 02:00 UTC; must not purge rows under an active hold |
| **Legal hold (required)** | Record an active hold for affected tenant / matter references through `matter_legal_holds` / `POST /api/v1/legal-holds` | **Schema/API LIVE:** tenant-scoped matter hold SSOT; **gap:** retention workers do not yet consult it, so operators must still pause affected purge jobs |
| **Evidence** | Pre-disposal `AuditLogEntry` + `AuditLogExport.file_hash` | Required before destructive steps where feasible |

**Scope boundary:** The hold register records and releases tenant-scoped instructions (`matter_reference` is generic because QGP has no canonical legal-matter model). It does not claim a legal assessment, automatically relabel existing evidence, or prevent every purge until workers consume active holds.

---

## 7b. Public retention disclosure API (Path-to-10 S15)

Machine-readable retention capability is exposed on `GET /api/v1/privacy/contact` under the **`retention`** key (additive to the existing `data_lifecycle` block from OCR/AI DPIA disclosure).

| Field | Source | Honesty contract |
| --- | --- | --- |
| `soft_delete_first` | `DEFAULT_RETENTION_POLICIES` (`RetentionPolicy.soft_delete_first`) | `true` when all coded entity policies prefer soft-delete before hard purge |
| `matter_level_legal_hold_schema` | Schema inventory | **`true`** — `matter_legal_holds` is the tenant-scoped SSOT |
| `matter_level_legal_hold_enforcement` | Retention worker integration | **`not_yet_wired_to_retention_workers`** — do not interpret schema/API availability as automated purge prevention |
| `entity_horizons_days` | `src/core/retention_config.DEFAULT_RETENTION_POLICIES` | Days per entity key — mirrors config SSOT, not a substitute for this policy narrative |
| `policy_doc` | This file | `docs/privacy/data-retention-policy.md` |
| `purge_schedule` | Celery Beat | Daily 02:00 UTC `run-data-retention` |

Operators and attestations can discover the hold SSOT and its enforcement boundary without opening the repo; they must still treat §7a as the legal-hold gap SSOT.

---

## 7. Roles and exceptions

- **Legal hold:** Suspend automated purge for affected tenants / matter IDs.
- **DPO approval:** Required for retention period **shortening** if it may destroy evidence subject to litigation.

---

## 8. Review

This policy is reviewed **annually** or when retention law or insurer requirements change.

**Last updated:** 2026-07-11

## DPIA close-out readiness

For S15 compliance scoring, the unsigned DPIA / Art. 30 attestation pack lives at
[`docs/compliance/s15-dpia-art30-attestation-pack.md`](../compliance/s15-dpia-art30-attestation-pack.md)
(platform DPIA §11 still indexes the same artifacts). This retention/legal-hold SSOT is an
input to that pack — it does not itself constitute DPO sign-off or close EA-03.

