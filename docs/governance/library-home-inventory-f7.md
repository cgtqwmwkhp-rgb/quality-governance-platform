# F-7 — Library multi-home inventory (disposition)

**Status:** Design inventory (Accepted dispositions; migrations land later)  
**Date:** 2026-08-09  
**Programme:** Library spine FIRST pack (with ADR-0023 / D14 / D15)  
**Rule:** Enhance existing homes; never add a new `file_path` / `storage_key`
table. F-3 gate + `library_anti_dupe_baseline.json` own the allowlist.

Disposition codes:

| Code | Meaning |
| --- | --- |
| **keep** | Remains SoT for that concern (or legitimate non-library concern) |
| **migrate** | Data / pointer converges onto library `documents` / CEL / category fields |
| **drop** | Retire after migration (or refuse new writes now; delete schema later) |

---

## 1) File homes

| Home | Columns | Role today | Disposition | Target |
| --- | --- | --- | --- | --- |
| `documents` | `file_path` | Library Document tip blob | **keep** | Register file SoT |
| `document_versions` | `file_path` | Immutable version blobs | **keep** | Version SoT under library doc |
| `controlled_documents` | `file_path` | Control-layer pointer / shell | **migrate** | Fold to `library_document_id` + library versions (Golden Thread); stop dual blob writes |
| `controlled_document_versions` | `file_path` | Control-layer version blobs | **migrate** | Prefer library `document_versions`; retain only if control-only artefacts remain after fold |
| `carbon_evidence` | `file_path`, `storage_key` | Planet Mark evidence blobs | **migrate** | Link / promote into Register (`documents.id`); keep PM metadata tables |
| `evidence_assets` | `storage_key`, `thumbnail_storage_key` | Investigation / case evidence | **migrate** | Remain case-scoped store short-term; optional `documents.id` link when filed to Library (no second Register) |
| `policy_versions` | `file_path` | Legacy policy version pointer | **migrate** → **drop** | Collapse into library docs/versions; then drop writes |
| `uvdb_*` `documents_presented` | JSON list (not a blob column) | UVDB pack presentation refs | **migrate** | Resolve to `documents.id` / CEL; JSON becomes projection, not file SoT |
| `compliance_schedule` OCR drafts | `source_storage_key` | Transient FRA OCR source | **keep** | Not a library home; filing copies into Library via explicit ADR-0020 step |
| `audit_log` attachments | `file_path` | Audit artefact (optional) | **keep** | Not Register; do not invent library twin |

Baseline allowlist today (F-3): `documents`, `document_versions`,
`controlled_documents`, `controlled_document_versions`, `carbon_evidence`,
`evidence_assets`, `policy_versions`. Shrinking that list is a success metric
for WI-2 / CUT — not this docs PR.

---

## 2) Retention homes

| Home | Columns | Role today | Disposition | Target |
| --- | --- | --- | --- | --- |
| `document_categories` | `retention_rule` (free text) | Taxonomy default prose | **migrate** | Machine-readable category defaults (`retention_years` + `retention_basis`) then copy onto document at file |
| `documents` | `retention_until` | Executable disposal candidate | **keep** | Single document-level retention clock for Library SoR |
| `controlled_documents` | `retention_period_years` | Parallel years integer | **migrate** | Derive from / sync to library document; stop independent SoR |
| `obsolete_document_records` | `retention_required`, `retention_end_date` | Obsolete control archive | **keep** (archive) | Archive concern after supersede — not a second live policy |
| `evidence_assets` | `retention_policy`, `retention_expires_at` | Case evidence retention | **keep** | Case/legal evidence policy; link to library only when filed |
| Audit log config | `retention_days` | Platform audit retention | **keep** | Not document library |

**Cutover gate (ADR-0023):** Citation SoR retirement requires executable
retention on library documents — free-text `retention_rule` alone is
insufficient.

---

## 3) Access homes

| Home | Columns | Role today | Disposition | Target |
| --- | --- | --- | --- | --- |
| `document_categories` | `default_access` | Filing default (`all_staff` / `managers` / `restricted`) | **keep** (default only) | Default at file time; not live ACL SoT |
| `documents` | `access_level` | Library document access | **keep** | Single live access field for Register documents |
| `controlled_documents` | `access_level` (`internal` default) | Parallel vocabulary | **migrate** | Align enum + sync from / to library; one vocabulary |
| `library_document_access_logs` | (log rows) | Library access audit | **keep** | Observability, not policy |
| `document_access_logs` (control) | (log rows) | Control-layer access audit | **migrate** / merge writers | Prefer one access-log spine once control folds |
| `iso27001` / `permissions` `access_level` | module ACL | Unrelated to library filing | **keep** | Out of Library programme scope |

---

## 4) Explicit non-goals

- Do **not** add another file-home table to “fix” UVDB/PM — link instead.
- Do **not** treat JL cells, Doc Graph edges, or CEL rows as file homes.
- Do **not** invent a second standards library for access/retention metadata.

## Implementation waves

| Wave | What moves |
| --- | --- |
| WI-2 | File-home links: carbon_evidence, UVDB presented, evidence_assets → `documents.id` |
| WC-1 / control converge | controlled_* file + access + retention sync |
| CUT-1 | Retention + access single SoR; Citation cutover |

## References

- Anti-dupe baseline: `docs/governance/library_anti_dupe_baseline.json`
- ADR-0023 (QGP SoR + retention executable gate):
  `docs/adr/ADR-0023-governance-library-reference-scheme.md`
- ADR-0021 Golden Thread:
  `docs/adr/ADR-0021-document-relationship-graph.md`
- Spec pack file SoT lock: `specs/governance-library/README.md`
