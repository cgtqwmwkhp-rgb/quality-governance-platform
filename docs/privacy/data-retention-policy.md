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

## 7. Roles and exceptions

- **Legal hold:** Suspend automated purge for affected tenants / matter IDs.
- **DPO approval:** Required for retention period **shortening** if it may destroy evidence subject to litigation.

---

## 8. Review

This policy is reviewed **annually** or when retention law or insurer requirements change.

**Last updated:** _[YYYY-MM-DD]_
