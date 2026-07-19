# Change Ledger (CL-UVDB-EXPORT)

**Path claim:** `feat/after-uvdb-export` (UVDB-EXPORT)

## File allowlist (exclusive)

- `src/domain/services/uvdb_protocol_export_service.py`
- `src/api/routes/uvdb.py`
- `tests/unit/test_uvdb_protocol_export_service.py`
- `tests/integration/test_uvdb_protocol_export.py`
- `tests/unit/test_planetmark_uvdb_route_harness.py`
- `frontend/src/api/uvdbClient.ts`
- `frontend/src/api/uvdbClient.test.ts`
- `frontend/src/pages/UVDBAudits.tsx`
- `frontend/src/pages/__tests__/UVDBAudits.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_uvdb_protocol_export.md`

**Zero overlap** with Planet Mark, document campaigns, AuditExecution, or parallel campaign lanes.

## 1) Summary

- **Feature / Change name:** UVDB-EXPORT — authenticated UVDB B2 protocol pack download (JSON + XLSX)
- **User goal:** Operators on `/uvdb?section=export` download a real authenticated protocol pack for offline review instead of a disabled placeholder CTA.
- **In scope:** `GET /api/v1/uvdb/protocol/export?format=json|xlsx`; export service; `uvdbClient.downloadProtocolPack()`; enabled export buttons; honesty that filled-audit/branded PDF are follow-on; unit + FE tests; Change Ledger
- **Out of scope:** Planet Mark; document campaigns; AuditExecution; filled-audit pack; branded PDF; tenant-scored audit export
- **Feature flag / kill switch:** None — additive authenticated export route; revert commit to disable

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Backend | `GET /protocol` only (structure JSON) | Adds `GET /protocol/export` with JSON/XLSX attachment + provenance headers |
| Export service | N/A | `uvdb_protocol_export_service.py` builds pack from `UVDB_B2_SECTIONS` |
| Frontend export section | Disabled button + “not wired” honesty | Live JSON + XLSX download buttons via authenticated blob export |
| i18n (en + cy) | Export unavailable copy | Export live; filled-audit/PDF follow-on honesty |
| Tests | Export button disabled assertion | Builder unit tests, route integration tests, client + page tests |

- **Frontend (routes/screens/components):** `UVDBAudits.tsx` export section; `uvdbClient.ts`
- **Backend (handlers/services):** `uvdb.py` export route; `uvdb_protocol_export_service.py`
- **APIs (endpoints changed/added):** `GET /api/v1/uvdb/protocol/export?format=json|xlsx` (default json)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Protocol pack JSON contract (`pack_version`, `exported_at`, `exported_by`, `follow_on_exports`, protocol structure)
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None (reuses existing `openpyxl`)

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive endpoint; existing `GET /protocol` unchanged in behaviour (refactored to shared builder)
- **Tolerant reader / strict writer applied?** Yes — export reuses static B2 sections SSOT; follow-on exports explicitly marked `not_available`
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert app deploy; no schema change

## 4) Acceptance Criteria (AC)

- [x] AC-01: `GET /api/v1/uvdb/protocol/export?format=json|xlsx` requires same auth as `GET /protocol`
- [x] AC-02: Export reuses `UVDB_B2_SECTIONS` / protocol structure payload with attributable `exported_at` + `exported_by`
- [x] AC-03: Response uses `Content-Disposition: attachment` (mirrors compliance audit-pack pattern)
- [x] AC-04: Frontend `uvdbClient.downloadProtocolPack()` downloads authenticated blob export
- [x] AC-05: `/uvdb` export section enables JSON + XLSX CTAs (no fake/disabled download)
- [x] AC-06: en + cy honesty states protocol export is live; filled-audit/branded PDF are follow-on
- [x] AC-07: Unit tests cover builder + route; FE tests cover client wiring and enabled export buttons

## 5) Testing Evidence (link to runs)

- [x] Unit — `tests/unit/test_uvdb_protocol_export_service.py`
- [x] Integration/route — `tests/integration/test_uvdb_protocol_export.py`
- [x] Frontend — `uvdbClient.test.ts`, `UVDBAudits.test.tsx`
- [ ] Full CI — linked after PR checks
- [ ] Staging smoke — deferred to Gate 3

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Operator opens `/uvdb?section=export` → sees live export honesty → downloads JSON pack
- [x] CUJ-02: Operator downloads XLSX pack with sections + questions sheets for offline review
- [x] CUJ-03: Export pack includes follow-on honesty for filled-audit/branded PDF (not offered yet)

## 7) Observability & Ops

- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Response header `X-UVDB-Protocol-Pack-Version`
- **Playwright hooks:** `uvdb-section-export`, `uvdb-export-protocol-honesty`, `uvdb-export-protocol-json`, `uvdb-export-protocol-xlsx`

## 8) Release Plan (Local → Staging → Canary → Prod)

- **Staging verification:** Authenticated download of JSON + XLSX from `/uvdb?section=export`; verify attachment filenames and pack contents
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Smoke `GET /api/v1/uvdb/protocol/export?format=json` with auth; spot-check `/uvdb?section=export`

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** Export route 5xx; unauthenticated download; corrupt/empty pack payload
- **Rollback steps:** Revert this PR deploy; export section returns to prior disabled state on old SHA
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)

- CI run(s): this PR checks
- Base branch: `main` @ `224b80b`
- Staging deploy evidence: pending

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
