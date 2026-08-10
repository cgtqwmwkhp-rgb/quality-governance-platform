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
| `document_categories` | `retention_rule` (free text) → **+ `retention_years`, `retention_anchor`** | Taxonomy default prose plus its machine-readable projection | **migrated (CUT-1)** | Projection derived by `library_retention_policy` at seed time; prose stays as the R19 basis, so there is no second text column |
| `documents` | `retention_until` → **+ `retention_years`, `retention_anchor`, `retention_basis`** | Executable disposal candidate + the policy that produced it | **keep** | Single document-level retention clock for Library SoR; policy copied on at file so a taxonomy edit cannot re-date filed documents |
| `controlled_documents` | ~~`retention_period_years`~~ | ~~Parallel years integer, `default=7` on every INSERT~~ | **dropped (CUT-1b)** | Gone (`20261104_lib_cut1b_drop`). The control record holds no retention fact of its own; retention is read from the anchored Register row |
| `obsolete_document_records` | `retention_required`, `retention_end_date` | Obsolete control archive | **keep** (archive) | Archive concern after supersede — not a second live policy. Since CUT-1b `retention_end_date` is derived from the Register row at obsolescence, and is NULL when the Register cannot answer |
| `evidence_assets` | `retention_policy`, `retention_expires_at` | Case evidence retention | **keep** | Case/legal evidence policy; link to library only when filed |
| Audit log config | `retention_days` | Platform audit retention | **keep** | Not document library |

**Cutover gate (ADR-0023):** Citation SoR retirement requires executable
retention on library documents — free-text `retention_rule` alone is
insufficient. **CUT-1 built the gate and made it answerable**:
`scripts/governance/library/citation_cutover_readiness.py` classifies every
filable category, and 14 of 73 still name two periods or a condition that no
single number can represent. Those are steward decisions, not code — documents
filed under them keep `retention_until` NULL and are never disposal candidates.
See `library-cut1-retention-access-sor.md`.

---

## 3) Access homes

| Home | Columns | Role today | Disposition | Target |
| --- | --- | --- | --- | --- |
| `document_categories` | `default_access` | Filing default (`all_staff` / `managers` / `restricted`) | **keep** (default only) | Default at file time; not live ACL SoT |
| `documents` | `access_level` | Library document access | **keep** | Single live access field for Register documents. Vocabulary now defined once, in `library_rules.LIBRARY_ACCESS_LEVELS` |
| `controlled_documents` | `access_level` (was `internal` default) | ~~Parallel vocabulary~~ | **migrated (CUT-1)** | Folded onto the Library vocabulary; an anchored control row takes the Register row's level, an off-vocabulary write is refused |
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
| CUT-1 | Retention + access single SoR; Citation cutover — **shipped** (`20261102_lib_cut1_sor`). Access folded; retention made executable with a named refusal where prose cannot be read. Remainder at the time: `controlled_documents.retention_period_years` column drop (done by CUT-1b), control access-log merge, and the 14 steward retention decisions (done by STEWARD-14) |
| STEWARD-14 / CIT-1 | The 14 steward retention decisions accepted and applied — **shipped** (`20261103_lib_steward14`). New home: `specs/governance-library/steward_retention_decisions.json` holds `taxonomy_id` → years + anchor + rationale, and *only* that; `taxonomy.json` `retention_rule` remains the prose authority and R19 basis, unedited. The §2 gate ("Citation SoR retirement requires executable retention") reports 0 blockers for all 73 filable categories and runs with `--fail-on-blockers` in `CI - Default`. Citation (ATLAS)'s flat 7-year position is retired for the Register. Remainder at the time: `controlled_documents.retention_period_years` column drop (done by CUT-1b, below), control access-log merge, legacy `documents.retention_*` backfill (CUT-1c) |
| CUT-1b | `controlled_documents.retention_period_years` dropped — **shipped** (`20261104_lib_cut1b_drop`). The column's `default=7` was a live writer, stamping Citation's flat seven years onto every controlled document; its only reader turned that into the obsolete archive's `retention_end_date` at `years * 365`. Both are gone: §2 now has exactly one retention SoR, and the archive date is derived from the Register row (`supersede_retention_until`) or left NULL. The old value is **not** migrated onto the Register — it was a constructor default, not a decision. Remainder: control access-log merge (§3), legacy `documents.retention_*` backfill (CUT-1c, deferred) |

## References

- CUT-1 converge design note: `docs/governance/library-cut1-retention-access-sor.md`
- Anti-dupe baseline: `docs/governance/library_anti_dupe_baseline.json`
- ADR-0023 (QGP SoR + retention executable gate):
  `docs/adr/ADR-0023-governance-library-reference-scheme.md`
- ADR-0021 Golden Thread:
  `docs/adr/ADR-0021-document-relationship-graph.md`
- Spec pack file SoT lock: `specs/governance-library/README.md`
