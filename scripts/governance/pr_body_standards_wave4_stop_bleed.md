# Change Ledger (CL-STANDARDS-WAVE4-STOP-BLEED)

> **Start gate:** Begin implementation only after **PR #1736 (Wave 3 PR-F3 digests) is LIVE** (main tip CI green → STG SHA = PROD SHA = tip). `STACK_MAX=1`.

## 1) Summary
- **Feature / Change name:** Standards Wave W4 — Stop the bleed (correctness only).
- **User goal:** A framework with no imported alignment / requirement pair must render **unknown** (not covered) and must **never** auto-confirm by borrowing an ISO EXACT row. Matrix paint and cert counts must stop lying across columns.
- **In scope (correctness fixes only):**
  - **F-1** TrapGuard + ingest gate: non-ISO cells (chas/ce/ssip/…) cannot inherit ISO `row_verdict=EXACT` with `peers=0`.
  - **F-2** Gate framework-blind suffix match so an ISO CEL cannot paint non-ISO matrix columns unless TrapGuard covers that framework.
  - **F-3** Remove `"register"` from every `FRAMEWORK_ALIASES.cert_schemes`; match register certs by `Certificate.certificate_type` → framework; unmatched → `proof_scope: "unmatched"` (excluded from `cert_count`).
  - **F-4** Unblock **All** preset (12×32 > 200 cell cap) so imported matrix does not degrade.
  - Surface `scan_truncated` on `get_cell` / `get_matrix_summary` when any source hits `limit(500)`; hover preview must say so.
  - UVDB shelf scheme mismatch: align `uvdb_achilles` (shelf stamp) with `uvdb` aliases so UVDB certs count on the UVDB column.
- **Out of scope:** W5 requirement catalogues / non-ISO axes; W6 alignment edges; W7 typed assessment cycles; W8 technical attestation; W9 IMS rebuild; W10 case auto-map; Constructionline; second analytics/surface; `/standards` revival; fake Full/Partial/Gaps %; loosening ≥98% + EXACT.
- **Surface lock:** Option A — `/compliance` only (Matrix / Evidence / existing Monitoring digests). No second surface.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changes)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W4-01 | TrapGuard `annotate_cell` | Bare `clause_ref` hands ISO row verdict to any framework | `frameworks_on_row` / `covers_framework`; no fallback unless cell FW is on the row → `row_verdict: null`, `alignment_known: false` |
| SG-W4-02 | Ingest gate auto-confirm | `row_verdict == "EXACT"` alone → `auto_confirm=True` (chas/ce/ssip peers=0) | EXACT **pair edge touching this cell's framework** required (`peers` contains EXACT peer); else `alignment_not_exact_for_framework` |
| SG-W4-03 | Cell aggregate token match | Framework-blind suffix paints ISO CEL across all columns | Suffix match gated on `guard.covers_framework(cell_fw)`; absent FW → only explicitly framed tokens match (bare `7.2` does **not** paint CHAS/CE/…) |
| SG-W4-04 | Cert proof / `FRAMEWORK_ALIASES` | `"register"` in almost every `cert_schemes` → whole register proves every FW | `"register"` removed; type→FW match; unmatched excluded from `cert_count` |
| SG-W4-05 | Matrix All preset | 12×32=384 > 200 → BadRequest → degraded matrix | Cap raised and/or preset-chunk / page token so `all` returns 200 OK with imported 32-row axis |
| SG-W4-06 | Cell honesty | Silent `limit(500)` truncation | `scan_truncated` on cell + matrix summary; hover states truncation |
| SG-W4-07 | UVDB cert column | Shelf stamps `uvdb_achilles`; aliases list `uvdb`/`achilles` → miss | Alias / scheme alignment so UVDB shelf proofs attach to UVDB column only |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Behavioural correctness; no schema / alembic required for core F-1–F-4. Additive response fields (`scan_truncated`, `proof_scope`) only.
- **Tolerant reader / strict writer?** FE tolerant of new optional flags; writers unchanged except gate refusal reasons.
- **Breaking changes:** Cells that previously auto-confirmed / painted green without a framework pair will correctly refuse / show unknown — intentional.
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| ≥98% + EXACT auto-confirm | Satisfied in form; broken in substance (peers=0 on non-ISO) | EXACT pair must touch cell framework; ISO EXACT paths unchanged |
| Cross-framework paint | ISO CEL paints non-ISO columns via suffix | Non-ISO columns unknown unless covered by TrapGuard / explicit FW token |
| Cert honesty | Register proves every framework | Typed match only; unmatched never inflate `cert_count` |
| Matrix All preset | Degrades after real import | Paints imported axis without degraded fallback |
| Fake % | Forbidden (prior waves) | Still forbidden — unknown ≠ 0% |

## 4) Acceptance Criteria (AC)
- [ ] AC-01: `chas-7.2` / `ssip-7.2` / `ce-7.2` at confidence 0.99 → `auto_confirm=False`, reason `alignment_not_exact_for_framework`; ISO `9001-7.2` still `True` when EXACT peers exist.
- [ ] AC-02: CEL on `9001-6.1.2` yields **unknown** on chas/ce/cep/iip/ssip/pm/uvdb and stays cover-blocked on 14001 (trap sheet 07 preserved ISO↔ISO).
- [ ] AC-03: CHAS cell with only a PAT (or other non-CHAS) register certificate → `cert_count: 0`; unmatched proofs carry `proof_scope: "unmatched"`.
- [ ] AC-04: `all` preset returns **200** with imported 32-row axis (no `standards-matrix-degraded-badge` solely due to cell count).
- [ ] AC-05: When any cell source hits `limit(500)`, response includes `scan_truncated=true` and hover preview discloses truncation.
- [ ] AC-06: UVDB Achilles shelf proofs match the UVDB column (`uvdb_achilles` ↔ `uvdb` aliases); do not attach to unrelated frameworks.
- [ ] AC-07: ≥98% + EXACT gate logic otherwise unchanged; Constructionline remains out; no fake coverage %.
- [ ] AC-08: No new page/route/nav entry; Option A `/compliance` only.
- [ ] AC-09: Existing PR-B/C/D/E (+ F3) unit tests still pass — **no tests loosened**.
- [ ] AC-10: Hosted CI green; STG=PROD tip LIVE after merge.

## 5) Testing Evidence (link to runs)
- [ ] Unit: `tests/unit/test_standards_trap_guard.py` — `covers_framework` / no ISO fallback for non-ISO cells
- [ ] Unit: `tests/unit/test_standards_ingest_gate.py` — peers=0 non-ISO refuse; ISO EXACT unchanged
- [ ] Unit: `tests/unit/test_standards_cell_aggregate_service.py` — suffix gate, cert_count, `scan_truncated`, UVDB alias
- [ ] Route/unit: matrix cap / All preset 12×32 path (`compliance.py` + FE chunk if used)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [ ] CUJ-01: Ingest / auto-confirm path for `chas|ce|ssip` clause at high confidence → refused; ISO EXACT peer path still confirms.
- [ ] CUJ-02: `/compliance?view=matrix` → All preset after alignment import → live graph (not degraded); hover a truncated cell → truncation disclosed.
- [ ] CUJ-03: CHAS (or CE) cell with only unrelated register cert → no inflated cert proof; UVDB column shows Achilles shelf cert when present.

## 7) Observability & Ops
- Prefer explicit refusal reasons (`alignment_not_exact_for_framework`) over silent deny.
- `scan_truncated=true` means the paint may under-count findings/actions/CELs — treat as honesty signal, not a green cell.
- Support: if non-ISO columns go unknown after deploy, that is expected until W5/W6 land catalogues + edges.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Wait for **#1736 LIVE**; branch from that tip (`STACK_MAX=1`).
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify matrix All + ingest refuse paths.
4. Promote PROD; verify health tip = main tip; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** ISO EXACT auto-confirm regresses; matrix All still degraded; cert_count wrong for legitimate ISO certs; paint falsely clears covered cells.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger (save later in-repo): `scripts/governance/pr_body_standards_wave4_stop_bleed.md`
- Parent LIVE gate: **PR #1736** (F3 digests)
- Clinical source: Standards integration clinical review (F-1…F-4, F-6 truncation, UVDB scheme mismatch)

## Files to touch (concrete)
| Area | Path |
|---|---|
| TrapGuard | `src/domain/services/standards_trap_guard.py` |
| Ingest gate | `src/domain/services/standards_ingest_gate.py` |
| Cell aggregate + `FRAMEWORK_ALIASES` | `src/domain/services/standards_cell_aggregate_service.py` |
| Matrix cell cap | `src/api/routes/compliance.py` (and FE preset-chunk if chosen) |
| UVDB shelf scheme (if fix lives at stamp) | `src/domain/services/assurance_cert_shelf_service.py` |
| Tests | `tests/unit/test_standards_trap_guard.py`, `tests/unit/test_standards_ingest_gate.py`, `tests/unit/test_standards_cell_aggregate_service.py` (+ route/FE tests as needed) |

## Gate checklist
- [ ] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1736 LIVE confirmed
- [ ] **Gate 1:** Focused unit tests green locally (no loosened baselines)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify (All preset + refuse paths + cert honesty)
- [ ] **Gate 4:** PROD tip verify (ACA image = tip SHA)
- [ ] **Gate 5:** Hero board / mission / allowlist updated after LIVE

---

## Appendix — Post-F3 queue (W4 → W10)

| Wave | Name | Goal (one line) | Depends |
|---|---|---|---|
| **W4** | **Stop the bleed** | Correctness: no borrowed EXACT, no cross-column paint, honest certs, All preset paints, truncation visible | **#1736 LIVE** |
| **W5** | Non-ISO requirement catalogues | Own axes (`ce-*`, `chas-*`, `ssip-*`, `iip-*`, UVDB B2, PM themes); 22301 first-class ISO | W4 |
| **W6** | Non-ISO alignment edges | EXACT/NEAR/DIFFERENT/UNIQUE pairs CE↔27001, SSIP/CHAS↔45001, IiP↔9001/45001, PM↔14001; ExactShare collation | W5 |
| **W7** | Cert + assessment cycle per FW | Typed shelf taxonomy + renewal/assessment; F3 cert digest feeds by scheme | W4 (∥ W5/W6) |
| **W8** | Technical attestation source | Real Entra/MFA (etc.) reader for CE/CEP; attestation-only `covered` | W5 |
| **W9** | IMS Overview on cell aggregate | Retire Control-count score; per-FW coverage/cert/NC; UVDB/PM tenancy | W5 |
| **W10** | Case auto-map across frameworks | Expand ISO matches via W6 edges; cases always `force_proposed` (never auto-apply) | W6 |

**Sequencing note:** W4 is mandatory groundwork. Shipping W5/W6 atop the current matcher would scale a wrong join across seven more frameworks and write fabricated confirmations into the audit trail.
