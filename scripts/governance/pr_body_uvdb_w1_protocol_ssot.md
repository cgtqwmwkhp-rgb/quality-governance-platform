# Change Ledger (CL-UVDB-W1-PROTOCOL-SSOT)

**Path claim:** `feat/uvdb-w1-protocol-ssot` (UVDB Wave 1)

## File allowlist (exclusive)

- `src/domain/uvdb/__init__.py`
- `src/domain/uvdb/protocol_b2_v118.py`
- `src/api/routes/uvdb.py`
- `src/domain/services/uvdb_protocol_export_service.py`
- `scripts/_generate_uvdb_protocol_ssot.py`
- `tests/unit/test_uvdb_protocol_ssot.py`
- `tests/unit/test_uvdb_protocol_export_service.py`
- `tests/integration/test_uvdb_protocol_export.py`
- `tests/integration/test_planetmark_uvdb_api.py`
- `frontend/src/api/uvdbClient.ts`
- `frontend/src/pages/UVDBAudits.tsx`
- `frontend/src/pages/__tests__/UVDBAudits.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_uvdb_w1_protocol_ssot.md`

**Zero overlap** with training-matrix, customer-audits, cert-shelf, or parallel campaign lanes.

## 1) Summary

- **Feature / Change name:** UVDB-W1 — versioned B2 protocol SSOT scaffolding with honest partial-load semantics
- **User goal:** `/uvdb` and export APIs expose the full 15-section B2 structure without implying sections 3–11 have copyrighted question text before v11.8 PDF ingest.
- **In scope:** Extract `UVDB_B2_SECTIONS` to `src/domain/uvdb/protocol_b2_v118.py`; keep loaded sections 1, 2, 12–15 as-is; add pending shells 3–11; `content_coverage` honesty fields; FE version badge + ISO summary fixes; unit/integration/vitest proofs; Change Ledger
- **Out of scope:** Achilles PQQ/payment clone; day-of audit workstation; inventing v11.8 question wording without SoR PDF; Wave 2 PDF ingest
- **Feature flag / kill switch:** None — static SSOT refactor; revert commit to disable

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Protocol SSOT | Inline list in `uvdb.py` (6 sections only) | `protocol_b2_v118.py` with 15 sections; `PROTOCOL_VERSION = "11.8-target"` |
| Loaded content | Sections 1, 2, 12–15 | Unchanged question text (moved as-is) |
| Missing sections | Absent (implicit gap) | Shells 3–11 with provisional titles + `content_status=pending_protocol_pdf` |
| API `/sections`, `/dashboard`, `/protocol`, `/iso-mapping` | Implied full protocol at V11.2 | `content_coverage` + honest ISO summaries for pending sections |
| Export pack | `uvdb-protocol-1.0`, V11.2 label | `uvdb-protocol-1.1`, `11.8-target`, coverage metadata, section status columns in XLSX |
| Frontend `/uvdb` | Static “Version 11.2” copy | Dynamic target version + partial-load banner; pending section cards |

- **Frontend:** `UVDBAudits.tsx`, `uvdbClient.ts`, i18n en/cy
- **Backend:** `protocol_b2_v118.py`, `uvdb.py`, `uvdb_protocol_export_service.py`
- **APIs:** Enriched contracts on existing UVDB protocol/sections/dashboard/iso-mapping/export routes (additive fields)
- **Database:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive metadata fields; existing loaded question payloads unchanged
- **Tolerant reader / strict writer:** Yes — consumers can read `content_status` / `content_coverage`; pending sections expose empty `questions`
- **Breaking changes:** Export pack version header bumped to `uvdb-protocol-1.1`; protocol `version` string now `11.8-target` (honesty fix, not a silent claim of full v11.8)
- **Migration plan:** None
- **Rollback strategy:** Revert deploy; prior 6-section inline SSOT returns

## 4) Acceptance Criteria (AC)

- [x] AC-01: `UVDB_B2_SECTIONS` lives in versioned SSOT module with `PROTOCOL_VERSION = "11.8-target"`
- [x] AC-02: Sections 1, 2, 12–15 question text moved unchanged
- [x] AC-03: Sections 3–11 exist as shells with provisional titles and no invented scoring text
- [x] AC-04: `/protocol`, `/protocol/export`, `/sections`, `/dashboard`, `/iso-mapping` consume SSOT and expose `content_coverage`
- [x] AC-05: FE removes overclaim (static V11.2 badge; ISO cards note pending PDF for 3–11)
- [x] AC-06: Unit + integration + Vitest expectations updated for 15 sections and honesty fields

## 5) Testing Evidence

- [x] `tests/unit/test_uvdb_protocol_ssot.py`
- [x] `tests/unit/test_uvdb_protocol_export_service.py`
- [x] `tests/integration/test_uvdb_protocol_export.py`
- [x] `tests/integration/test_planetmark_uvdb_api.py::TestUvdbApiContracts`
- [x] `frontend/src/pages/__tests__/UVDBAudits.test.tsx`, `frontend/src/api/uvdbClient.test.ts`
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Operator opens `/uvdb` → sees 15 sections with partial-load honesty banner
- [x] CUJ-02: Operator expands section 3 → sees pending PDF message (no fake questions)
- [x] CUJ-03: Operator downloads protocol JSON/XLSX → pack includes 15 sections + `content_coverage`

## 7) Observability & Ops

- **Logs / Metrics / Alerts:** No change — static SSOT module; existing UVDB route logging unchanged
- **Runbook updates:** N/A (Wave 2 PDF ingest will extend ops notes)

## 8) Release Plan (Local → Staging → Canary → Prod)

- **Staging verification:** Open `/uvdb`; confirm 15-section layout, partial-load banner, pending section 3 card
- **Canary plan:** N/A — additive metadata; no feature flag
- **Prod post-deploy checks:** Protocol JSON/XLSX export includes `content_coverage`; version shows `11.8-target`

## 9) Still needs v11.8 PDF (Wave 2)

- Official section titles pin for sections 3–11 (currently `title_provisional=true`)
- Full question / sub-question / evidence / scoring text for sections 3–11
- Accurate `max_score` per section for 3–11
- ISO cross-mapping rows for pending-section questions
- `content_coverage.status` transition from `partial` → `complete`

## 10) Rollback Plan (Mandatory)

- **Rollback trigger:** Incorrect section ordering; export pack regression; FE misstates coverage
- **Rollback steps:** Revert this PR deploy
- **Owner:** David Harris / Platform ops

## 11) Evidence Pack (links)

- CI run(s): Linked on PR checks
- Unit/integration/Vitest paths listed in Testing Evidence above

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts — additive `content_coverage` on existing UVDB routes
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — skip when not used)
- [x] **Gate 5:** Production verification plan ready
