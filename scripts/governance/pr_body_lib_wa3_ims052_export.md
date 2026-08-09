# Change Ledger (CL-LIB-WA3-IMS052-EXPORT)

## 1) Summary
- **Feature / Change name:** Library SECOND belt WA-3 — IMS052 Register export + containment / a11y gates (L-07 / L-08)
- **User goal (1–2 lines):** An auditor can download a Master Document Register evidence pack that always matches the fixed IMS052 column contract (PEL + legacy headers + control fields), regardless of what the Register UI happens to show; Register cells no longer bleed, status is greyscale + SR-legible, and Open links have unique accessible names.
- **In scope:** Enhance Export Center `documents` module into the IMS052 Register pack (csv / xlsx / pdf); fixed 15-column contract that rejects column pickers; active-only + library ACL narrowing so export ≈ Register estate; Register FE containment + greyscale status + caption / `scope="col"` / unique Open aria-labels
- **Out of scope:** Function / Category column cosmetics on the Register (WD-1 / later); Owner column (D3); derived control status (L-02); legacy IMS/PLA data backfill (no fields exist — headers stay empty); Function/PEL allocator changes (WA-2 DONE); DocumentDetail diet (WB-1); second export module / twin Register
- **Feature flag / kill switch:** None. Documents export shape change is deliberate and declared breaking for the previous 6-column CSV; other Export Center modules unchanged (csv only).

## 2) Impact Map (what changed)
- **Frontend:** `Documents.tsx` (containment widths/truncate/overflow, greyscale `RegisterStatusBadge`, table caption + `scope="col"`, unique Open `aria-label`); `documentsRegisterHelpers.ts` (`documentRegisterStatusTone`); i18n `en.json` / `cy.json` (`documents.table.caption`, `documents.table.open_aria`)
- **Backend:** `document_register_export.py` (new IMS052 helper); `export_center_service.py` (documents via `rows_builder`, per-module formats, `SyncExportResult.content` bytes); `exports.py` schema (`ExportFormat` gains xlsx/pdf; extra=forbid documents column pickers); `routes/exports.py` (streams bytes + passes user for ACL)
- **APIs:** `POST /api/v1/exports` and `GET /api/v1/exports/{module}/csv` — `format` may be `csv|xlsx|pdf` for `documents`; other modules remain csv-only; request bodies still forbid `columns` / `fields` / `visible_columns`
- **Database:** None — no Alembic
- **Config/env/flags:** None
- **Dependencies:** None new (openpyxl + fpdf2 already locked)
- **Tests:** `test_document_register_export.py` (new); `test_export_center_service.py`; `test_create_export_request_extra_forbid.py`; `test_export_center_api.py`; FE `documentsRegisterHelpers.test.ts`; `Documents.a11y.test.tsx` (pathological containment / greyscale / unique Open)
- **Docs:** this Change Ledger
- **Contract baseline:** `openapi-baseline.json` and `docs/contracts/openapi.json` refreshed together — `ExportFormat` enum widened; `CreateExportRequest` description notes picker forbid; documents catalog formats advertise csv/xlsx/pdf

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Non-documents modules keep the prior CSV shape. Documents CSV is a **declared breaking** shape change: the old `id,reference_number,title,status,file_name,created_at` header is replaced by the locked IMS052 15-column header so one SoT matches the fixture. Callers that parsed the old documents CSV must switch to the new headers (or use xlsx).
- **Breaking changes:** Documents export column contract only. `SyncExportResult` now carries `content: bytes` + `media_type` (route-internal; OpenAPI still streams a file attachment).
- **Migration plan:** N/A — no schema.
- **Rollback strategy (DB):** N/A.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| IMS052 evidence pack (L-07) | Documents CSV was a thin metadata dump; no XLSX/PDF; no PEL/legacy/review/access/retention | Fixed IMS052 header; csv + xlsx + pdf from one row builder |
| Export ignores UI column picker | No picker existed, but request could theoretically grow one | `extra=forbid` rejects `columns`/`fields`/`visible_columns`; builder takes no column arg; tests lock header |
| Export estate vs Register (D1) | Export listed inactive rows and skipped library ACL | Active-only + `user_can_read_library_document` narrowing (same rule as list) |
| One export SoT (enhance ≠ replicate) | Export Center `documents` module | Same module id, enhanced — no `documents_ims052` twin |
| Containment (L-08) | Sticky Document cell unbounded; pathological titles widen columns | Fixed max widths, truncate + `title`, overflow hidden |
| Status a11y (L-08) | Colourful Badge variants as sole cue | Greyscale `closed` + distinct icon + `aria-label` |
| Keyboard / SR (L-08) | Duplicate "Open" link names | Unique `Open {ref} — {title}`; caption + column scopes |

## 4) Acceptance Criteria (AC)
- [x] AC-01 (L-07): Documents export always emits the locked IMS052 15-column header (PEL, Legacy IMS/PLA empty, Document Name, Reference, Issue, Status, Function, Category, Last/Next Review, Location, Access Rights, Retention, Hyperlink) — never a UI column subset
- [x] AC-02 (L-07): Same rows serialize to csv, xlsx, and pdf; CreateExportRequest rejects `columns` / `fields` / `visible_columns` with ValidationError
- [x] AC-03 (L-07): Documents export includes only `is_active` documents the caller may read under library ACL; inactive / ACL-denied rows are omitted
- [x] AC-04 (L-08): Register status badges are greyscale (`closed`) with an icon + SR label — colour is not the sole cue
- [x] AC-05 (L-08): Pathological titles / uploader names truncate inside fixed cell widths; Open links have unique accessible names; table has caption + `scope="col"`
- [x] AC-06: No twin Register / twin export module; library anti-dupe gate reports 0 critical; no Alembic

## 5) Testing Evidence (link to runs)
- [x] `pytest tests/unit/test_document_register_export.py tests/unit/test_export_center_service.py tests/unit/test_create_export_request_extra_forbid.py tests/integration/test_export_center_api.py` — 28 passed (local)
- [x] `vitest` Documents + helpers + ExportCenter — 24 passed (local)
- [x] `black` / `isort` / `flake8` clean on touched Python
- [x] `python3 scripts/governance/library/anti_dupe_gate.py` — run on PR prep
- [x] OpenAPI baselines refreshed and equal
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor exports Documents from Export Center as CSV → file is `ims052_document_register_*.csv` with the full IMS052 header including PEL and Hyperlink, even though the Register UI shows a different column set
- [x] CUJ-02: Same export as XLSX → sheet `IMS052 Register` freezes header row; body matches CSV rows
- [x] CUJ-03: Request body with `columns: ["Document Name"]` is refused (422) — picker cannot shrink the pack
- [x] CUJ-04: Restricted Occupational Health document is omitted from the pack for a staff user without `document:restricted:oh`
- [x] CUJ-05: Register list with a 500-char title keeps the sticky Document cell contained; status reads greyscale with icon; Open announces PEL + title to SR

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None new. Existing export response headers (`X-Export-Row-Count`, `X-Export-Truncated`, `X-Export-Module`) unchanged.
- **Runbook updates:** None. Export Center Documents card description now states IMS052 fixed columns.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Ship with tip; no flag flip.
- **Canary plan:** N/A — additive formats on documents; breaking documents CSV shape is intentional and called out above.
- **DONE bar:** Conveyor marks WA-3 PROD/DONE only after tip SHA is LIVE on ACA and health is verified.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Documents export regressions for auditors, ACL over-filtering, or FE Register layout breakage.
- **Rollback steps:** Revert the merge and redeploy the prior tip. No DB rollback. Prior tip restores the 6-column documents CSV.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: After merge tip chase
- Canary evidence (if applicable): N/A
- Acceptance notes: L-07/L-08 from `library-world-class-ux-plan`; conveyor WA-3; enhance Export Center documents module — never a second export SoT. Legacy IMS/PLA columns are structurally empty until a future backfill (no model fields today). PDF is a landscape subset of columns for printability; XLSX/CSV carry the full 15-column contract.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — one documents export SoT, picker forbidden, Register containment/a11y
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge; Export Center documents csv/xlsx smoke
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE before DONE
