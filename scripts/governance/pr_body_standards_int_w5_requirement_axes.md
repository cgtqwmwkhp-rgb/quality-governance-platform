# Change Ledger (CL-STANDARDS-INT-W5-REQUIREMENT-AXES)

> **Start gate:** Int-W4 (#1737) LIVE — tip `07e14e4a4b17`. `STACK_MAX=1`.

## 1) Summary
- **Feature / Change name:** Standards Int-W5 — Non-ISO requirement catalogues + ISO 22301 first-class.
- **User goal:** Each non-ISO matrix column has its **own** requirement rows (what the scheme asks for). ISO 22301 joins the other ISOs in Evidence / coverage. Cross-framework share / auto-confirm remains edge-driven (W6).
- **In scope:** Requirement axes SSOT; isolated `standards_requirement_axis` module; seed migration; alignment catalogue `axis_frameworks` + `requirement_axes`; additive cell `axis` block; 22301 in `ISOStandard` / `ALL_CLAUSES` / aliases / FE Evidence bridge.
- **Out of scope:** W6 EXACT/NEAR edges; Constructionline; `/standards` revival; fake Full/Partial/Gaps %; loosening ≥98%+EXACT; changing TrapGuard `covers_framework` semantics.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

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
- **Coverage denominator:** adding ISO 22301 level-2 clauses into `ALL_CLAUSES` increases the global `/compliance/coverage` denominator for tenants that previously omitted BCMS — intentional honesty correction (record before/after on STG verify).
- **Tolerant reader / strict writer applied?** FE tolerant of additive `axis` / `requirement_axes`; writers unchanged except seed inserts.
- **Breaking changes:** None intentional for verdicts; coverage % may drop when 22301 enters the denominator.
- **Migration plan:** `alembic/versions/20261112_standards_w5_requirement_axes.py` (insert-only).
- **Rollback strategy (DB):** Downgrade removes W5 codes/keys only; UVDB/PM shells retained.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| ≥98% + EXACT auto-confirm | W4 peer-for-framework | Unchanged — catalogues do not create peers |
| Cross-column paint | Framed tokens for non-covered FWs | Unchanged — `covers_framework` still alignment-only |
| Non-ISO requirement truth | Absent | Own axes with provenance / content_status |
| 22301 Evidence | Not bridged | `iso22301` |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `TrapGuard.covers_framework("chas")` remains False when only a CHAS catalogue exists (no edges).
- [x] AC-02: `standards_requirement_axis` is not imported by `standards_trap_guard` or `standards_ingest_gate` (AST test).
- [x] AC-03: IiP catalogue keys include `iip-IIP 3` and `iip-IIP 7` (5064 edge join shape).
- [x] AC-04: UVDB axis derives from `UVDB_B2_SECTIONS`; pending sections stay `pending_protocol_pdf`; no invented completeness %.
- [x] AC-05: Alignment catalogue returns `axis_frameworks` + `requirement_axes` in loaded and empty branches; IIP 3/7 dedupe against alignment.
- [x] AC-06: Cell payloads gain additive `axis`; CHAS `7.2` verdict remains `unknown` under W4 rules.
- [x] AC-07: ISO 22301 is first-class (`ISOStandard`, `ALL_CLAUSES`, seed, `FRAMEWORK_ALIASES["22301"]["iso"]="iso22301"`, FE bridge).
- [x] AC-08: No new `alignment_edges`; Constructionline absent; ≥98%+EXACT unchanged.
- [ ] AC-09: Hosted CI green; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_requirement_axis.py`
- [x] Unit: `tests/unit/test_standards_w5_axis_isolation.py`
- [x] Updated: `test_iso_compliance_service.py`, `test_lib_wi1_cel_harden_scheme.py`
- [x] W4 suites unedited and green locally: trap_guard / ingest_gate / cell_aggregate (95 passed)
- [x] Vitest: `standardsMatrixFilters.test.ts` (22301 bridge)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/compliance` matrix — non-ISO columns do not borrow ISO EXACT; own catalogue keys exist for scheme rows.
- [x] CUJ-02: Evidence / list standards can resolve `22301` → `iso22301`.
- [x] CUJ-03: Monitoring digests (#1736) and W4 refuse paths unchanged.

## 7) Observability & Ops
- `axis.in_axis=false` means the clause number is not on that framework's requirement/alignment axis — do not treat as covered.
- UVDB `pending_protocol_pdf` rows are structural honesty, not gaps to invent text for.
- Support: coverage % may drop after 22301 enters `ALL_CLAUSES` denominator — expected.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `07e14e4a4b17` (`STACK_MAX=1`) — done.
2. Implement + focused unit green; open PR with this ledger — done (#1738).
3. Merge after CI green; STG verify axes + 22301 bridge + W4 refuse still holds.
4. Promote PROD; verify health tip = main tip; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** TrapGuard / ingest auto-confirm regresses; non-ISO columns paint from bare ISO tokens again; seed duplicates / migration fails; coverage tooling crashes on 22301.
- **Rollback steps:** Revert merge; redeploy prior tip `07e14e4a4b17` via governed Staging → Production; run migration downgrade if needed.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_int_w5_requirement_axes.md`
- Spec: `specs/standards/requirement-axes-v1.json`
- Parent LIVE gate: **PR #1737** (Int-W4 Stop the bleed) @ `07e14e4a4b17`
- Digests LIVE history: **PR #1736**

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1737 LIVE confirmed
- [x] **Gate 1:** Focused unit tests green locally (W4 baselines unloosened)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify (axes + 22301 + refuse paths)
- [ ] **Gate 4:** PROD tip verify (health SHA = tip)
- [ ] **Gate 5:** Master conveyor updated after LIVE
