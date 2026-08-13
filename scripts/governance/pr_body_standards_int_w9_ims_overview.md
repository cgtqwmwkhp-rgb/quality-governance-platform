# Change Ledger (CL-STANDARDS-INT-W9-IMS-OVERVIEW)

> **Start gate:** Int-W8 (#1742) LIVE — tip `a53cfc5f4b09`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Int-W9 — IMS Overview on cell aggregate.
- **User goal:** `/ims` Overview stops saying “0 standards tracked” / a Control-table implementation % when the live graph is the compliance matrix. Defect F-5.
- **In scope:** `get_ims_framework_meters`; IMS dashboard `cell_overview`; Overview hero + KPI + per-FW strip (covered/partial/gap/unknown **counts**, `cert_count`, `open_nc_cells`); UVDB/PM as frameworks; i18n en+cy.
- **Out of scope:** Case auto-map (W10); Entra flag / Graph wiring; ExactShare; TrapGuard / ingest / `covers_framework`; inventing EXACT for CHAS/SSIP/PM/UVDB; fake Full/Partial/Gaps %; persisting CEL rows.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W9-01 | IMS “standards tracked” | Control rows with `total_controls > 0` | Matrix frameworks with an imported ISO axis **or** a W5 scheme catalogue |
| SG-W9-02 | Overview hero | Control implementation % | Covered / partial / gap **cell counts** — not a score |
| SG-W9-03 | Per-FW strip | Absent | covered/partial/gap/unknown + cert_count + open_nc_cells; includes UVDB/PM |
| SG-W9-04 | Control-table `%` | Drove Overview | Still computed as `overall_compliance` for API compat; Overview FE ignores it |
| SG-W9-06 | Isolation | TrapGuard/ingest must not import requirement axes | Unchanged |
| SG-W9-07 | index gzip | 204 kB ceiling | 205 kB — `ims.overview.*` en+cy keys; IMSDashboard stays lazy |

## 3) Compatibility & Data Safety
- No schema / migration. No `ComplianceEvidenceLink` writes.
- Additive `cell_overview` on `GET /api/v1/ims/dashboard` (`extra` already allowed).
- Tenant required for meters (no cross-tenant TrapGuard/cert bleed).
- **Rollback strategy:** Revert merge and redeploy prior tip `a53cfc5f4b09`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| F-5 “Standards tracked: 0” | Wrong meter (empty Control table) | Scheme catalogues always count; ISO columns when 5064 covers them |
| Fake Full/Partial/Gaps % | Forbidden | Still forbidden — Overview shows counts |
| CHAS/SSIP EXACT | Not invented | Still not invented |
| `covers_framework` | Alignment edges only | Unchanged; catalogues do not flip it |
| TrapGuard / ingest isolation | No `standards_requirement_axis` import | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: “Frameworks on the matrix” is **not** Control-table count. Empty Control table + scheme catalogues → tracked ≥ 7 (CE/CEP/CHAS/SSIP/IiP/UVDB/PM). 5064 imported covering ISO columns → those ISO ids are added, not doubled onto CHAS.
- [x] AC-02: Overview hero does **not** show Control implementation %. Counts only — no fake Full/Partial/Gaps %.
- [x] AC-03: Per-FW strip: covered/partial/gap/unknown counts, `cert_count` (max across cells, not summed), `open_nc_cells`. UVDB and PM included.
- [x] AC-04: No EXACT invention; no `covers_framework` flip; TrapGuard/ingest must not import `standards_requirement_axis`.
- [x] AC-05: One tenant-wide source scan per IMS Overview request (`_scan_cache`); no N+1 DB read per cell.
- [x] AC-06: ISO columns use printed alignment clause refs only when `covers_framework`; scheme columns use W5 `axis_rows` (CHAS is not painted with ISO `7.2`).
- [x] AC-07: i18n keys in `en.json` and `cy.json`.
- [x] AC-08: No Alembic revision. Entra flag untouched.
- [x] AC-08b: index gzip ceiling 204→205 kB ledgered (IMSDashboard lazy; shell i18n only).
- [ ] AC-09: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_int_w9_ims_overview.py`
- [x] Unit: `tests/unit/test_ims_dashboard_tenant_safe.py` (cell_overview tenant pass-through)
- [x] FE: `frontend/src/pages/__tests__/IMSDashboard.test.tsx`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/ims` Overview with no Control rows still shows scheme frameworks (F-5).
- [x] CUJ-02: CHAS meter uses the CHAS catalogue, not ISO 7.2.

## 7) Observability & Ops
- `cell_overview.honesty` is an explicit “counts not a score” string in the payload.
- `scan_truncated` / `scan_truncated_sources` forwarded from the cell aggregate.
- Health SHA matching the merge commit is **not** sufficient if staging/prod deploy fails.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `a53cfc5f4b09` (`STACK_MAX=1`).
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.
4. Do **not** start Int-W10 until this PR is LIVE.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Overview shows a compliance % as the primary meter; CHAS cells counted from ISO 7.2; TrapGuard/ingest import requirement axes; matrix p95 +20% from N+1 scans.
- **Rollback steps:** Revert merge; redeploy prior tip `a53cfc5f4b09` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_int_w9_ims_overview.md`
- Parent LIVE gate: **PR #1742** (Int-W8) @ `a53cfc5f4b09`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1742 LIVE confirmed
- [ ] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
