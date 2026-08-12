# Change Ledger (CL-STANDARDS-INT-W5-REQUIREMENT-AXES)

> **Start gate:** Int-W4 (#1737) LIVE — tip `07e14e4a4b17`. `STACK_MAX=1`.

## 1) Summary
- **Feature / Change name:** Standards Int-W5 — Non-ISO requirement catalogues + ISO 22301 first-class.
- **User goal:** Each non-ISO matrix column has its **own** requirement rows (what the scheme asks for). ISO 22301 joins the other ISOs in Evidence / coverage. Cross-framework share / auto-confirm remains edge-driven (W6).
- **In scope:** Requirement axes SSOT; isolated `standards_requirement_axis` module; seed migration; alignment catalogue `axis_frameworks` + `requirement_axes`; additive cell `axis` block; 22301 in `ISOStandard` / `ALL_CLAUSES` / aliases / FE Evidence bridge.
- **Out of scope:** W6 EXACT/NEAR edges; Constructionline; `/standards` revival; fake Full/Partial/Gaps %; loosening ≥98%+EXACT; changing TrapGuard `covers_framework` semantics.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W5-01 | TrapGuard `covers_framework` | Alignment-only | Unchanged (docstring clarifies catalogues never flip it) |
| SG-W5-02 | Requirement axes module | Absent | `has_requirement_axis` / axis rows; AST-isolated from TrapGuard + ingest |
| SG-W5-05 | Scheme catalogues | Chrome columns only | `ce/cep/chas/ssip/iip/uvdb/pm` own keys; IiP keys match 5064 `iip-IIP 3/7` |
| SG-W5-06 | UVDB | Protocol SSOT only | Axis derived from `UVDB_B2_SECTIONS`; pending sections stay `pending_protocol_pdf` |
| SG-W5-07 | Alignment catalogue API | Rows without axis metadata | `axis_frameworks` + `requirement_axes` (loaded + empty branches) |
| SG-W5-08 | Cell aggregate | Verdict only | Additive `axis` block; CHAS `7.2` still `unknown` |
| SG-W5-09 | ISO 22301 | Matrix peer only | First-class ISO — enum, clauses, seed, `iso22301` alias, FE bridge |
| SG-W5-13 | Alignment edges | W4 set | **No new edges** |

## 3) Compatibility & Data Safety
- Additive API fields; insert-only seed by `catalogue_key` / `code`.
- **Coverage denominator:** adding ISO 22301 level-2 clauses into `ALL_CLAUSES` increases the global `/compliance/coverage` denominator for tenants that previously omitted BCMS — intentional honesty correction (ledger this on verify).
- Rollback: revert merge; migration downgrade removes W5 codes/keys only.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| ≥98% + EXACT auto-confirm | W4 peer-for-framework | Unchanged — catalogues do not create peers |
| Cross-column paint | Framed tokens for non-covered FWs | Unchanged — `covers_framework` still alignment-only |
| Non-ISO requirement truth | Absent | Own axes with provenance / content_status |
| 22301 Evidence | Not bridged | `iso22301` |

## 4) Acceptance Criteria (AC)
- [x] SG-W5-01 … SG-W5-13 as designed (see unit/AST tests).
- [ ] Hosted CI green; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence
- Unit: `tests/unit/test_standards_requirement_axis.py`
- Unit: `tests/unit/test_standards_w5_axis_isolation.py`
- Updated: `test_iso_compliance_service.py`, `test_lib_wi1_cel_harden_scheme.py`
- Vitest: `standardsMatrixFilters.test.ts` (22301 bridge)
- W4 suites **unedited**: trap_guard / ingest_gate / cell_aggregate

## 6) CUJ
- CUJ-01: `/compliance` matrix — CHAS/CE/SSIP columns no longer borrow ISO EXACT; own catalogue keys exist for scheme rows.
- CUJ-02: Evidence / list standards can resolve `22301` → `iso22301`.
- CUJ-03: Monitoring digests (#1736) unchanged.

## 7) Release
1. Merge tip after CI green.
2. Staging then Production deploy.
3. Verify `GET /api/v1/health` version on STG=PROD=tip.
4. Only then open Int-W6.
