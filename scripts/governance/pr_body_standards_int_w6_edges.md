# Change Ledger (CL-STANDARDS-INT-W6-EDGES)

> **Start gate:** Int-W5 (#1739) LIVE — tip `903adf53cae4`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Int-W6 — Non-ISO alignment edges (structural + CE↔CE+ NEAR).
- **User goal:** Alignment lookup actually finds IiP peers; CE/CE+ share as NEAR (Plus = independent verification); ExactShare lands in Exceptions as proposed, not confirmed coverage.
- **In scope:** Lowercase alignment lookup; scheme columns always require framed tokens; 5064 v1.1 CE↔CE+ NEAR ×5; ExactShare `PROPOSED` + `auto_applied`; scheme-axis band on the matrix; Dockerfile COPY of v1.1 JSON.
- **Out of scope:** Invented EXACT for CHAS/SSIP/PM/UVDB; `/standards` hub; loosening ≥98%+EXACT; flipping TrapGuard `covers_framework` semantics for catalogues.
- **Feature flag / kill switch:** None. Revert this PR. Re-seed 5064 v1.0 if a tenant has already applied v1.1.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W6-01 | TrapGuard lookup | `clause_key` case-preserving vs stored lowercase → IiP peers empty | `alignment_clause_key` lowercases; `clause_key` unchanged for W5 catalogues |
| SG-W6-02 | Framed tokens | `not covers_framework` | Scheme numbering family always framed; ISO family still uses `covers_framework` |
| SG-W6-03 | 5064 payload | v1.0 | v1.1 same `source_ref`; five CE↔CE+ NEAR pairs; CHAS/SSIP/PM/UVDB `declared_absent` |
| SG-W6-04 | Ingest auto-confirm | Any EXACT peer | Intra-ISO-family EXACT peer only; `iip-IIP 7` does not machine-confirm |
| SG-W6-05 | ExactShare apply | MANUAL → CONFIRMED | `status=PROPOSED`, `auto_applied=True`; cell aggregate excludes those from conformance |
| SG-W6-06 | Matrix FE | Scheme rows stripped | CE/CE+ axis band; only owning columns clickable |
| SG-W6-07 | Dockerfile | v1.1 JSON not in image | COPY + unit pin (W5 class of miss) |
| SG-W6-08 | EXACT for CE/CHAS/SSIP/PM/UVDB | None | Still none |

## 3) Compatibility & Data Safety
- Additive columns: `matrix_versions.coverage_declarations`, `alignment_edges.source_authority`.
- New matrix edition via existing import/seed (`source_ref` unchanged). Tenants on v1.0 stay on v1.0 until `seed_5064_alignment` / import apply of v1.1.
- **Tolerant reader / strict writer applied?** FE tolerant of additive `kind=scheme` rows and `axis_frameworks`.
- **Breaking changes:** ExactShare no longer auto-confirms shared links (empty set in prod today). Scheme columns require framed tokens even after CE edges load (W4 honesty held).
- **Migration plan:** `alembic/versions/20261113_standards_w6_alignment_edges.py` (add columns only). Then re-seed 5064 v1.1 per tenant.
- **Rollback strategy (DB):** Downgrade drops the two columns. Re-apply v1.0 payload to supersede v1.1.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| ≥98% + EXACT auto-confirm | EXACT peer of any family | ISO-family EXACT peer only |
| Cross-column paint | Framed tokens iff not `covers_framework` | Scheme family always framed — CE edges cannot reopen W4 |
| CE ↔ CE+ | No pairs | NEAR + addition_text; ingest refuses auto-confirm |
| ExactShare | Confirmed coverage | Proposed / Exceptions only |
| CHAS/SSIP/PM/UVDB EXACT | Absent | Declared-absent; not invented |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `annotate_cell(iip, "IIP 7")` returns ISO EXACT peers (lookup no longer dead).
- [x] AC-02: `clause_key("iip", "IIP 7")` remains `iip-IIP 7`.
- [x] AC-03: `covers_framework("ce")` is True after v1.1; `requires_framed_tokens` still True for ce and chas.
- [x] AC-04: Bare `7.2` still does not match CHAS or CE cells.
- [x] AC-05: Auto-confirm set: ISO EXACT cells still confirm; `iip-IIP 7` does not; `ce-firewalls` @0.99 → `alignment_near_requires_addition`.
- [x] AC-06: Zero EXACT edges naming ce/cep/chas/ssip/pm/uvdb.
- [x] AC-07: ExactShare apply writes `PROPOSED` + `auto_applied=True`; writer unit pin.
- [x] AC-08: Dockerfile copies v1.1 JSON; alembic single head `20261113_standards_w6_edges`.
- [x] AC-09: TrapGuard / ingest gate still do not import `standards_requirement_axis`.
- [ ] AC-10: Hosted CI green; STG migrations success; STG health SHA = PROD health SHA = tip → LIVE / DONE.
- [ ] AC-11: After LIVE, re-seed 5064 v1.1 on the production tenant so CE band is not just code.

## 5) Testing Evidence (link to runs)
- [x] Unit: trap_guard / ingest_gate / cell_aggregate / alignment_import / exact_share / dockerfile / w5 isolation / w6 payload (140 passed locally)
- [x] Unit: CEL create-only proposed+auto_applied
- [ ] Vitest: `standardsMatrixFilters.test.ts` (scheme band + clickable)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/compliance` matrix — ISO axis unchanged; CE/CE+ firewalls row is a scheme band, not mixed into 4.1–10.3.
- [x] CUJ-02: CE 7.2 remains unknown (no borrowed ISO EXACT).
- [x] CUJ-03: ExactShare cannot paint confirmed coverage on the destination cell.

## 7) Observability & Ops
- After deploy, **re-run** `python -m scripts.governance.standards.seed_5064_alignment --tenant-id <id>` so the live edition is v1.1. Code without re-seed leaves tenants on v1.0 (IiP lookup fix still applies to stored lowercase keys; CE band will not appear until v1.1 is applied).
- `coverage_declarations.chas.status=declared_absent` is honesty, not a gap to invent EXACT for.
- Health SHA matching the merge commit is **not** sufficient if staging migrations fail (W5 lesson).

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `903adf53cae4` (`STACK_MAX=1`) — done.
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify migrations + seed v1.1 + W4 refuse still holds.
4. Promote PROD; verify health tip = main tip **and** Azure Staging/Prod success; re-seed v1.1; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CE/CHAS cells paint from bare ISO tokens; auto-confirm expands; ExactShare confirms coverage; staging FileNotFound on v1.1 JSON; migration fails.
- **Rollback steps:** Revert merge; redeploy prior tip `903adf53cae4` via governed Staging → Production; if v1.1 was seeded, re-apply v1.0 payload; downgrade `20261113_standards_w6_edges` only if columns must go.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_int_w6_edges.md`
- Spec: `specs/standards/pel-hseq-5064-alignment-v1.1.json`
- Parent LIVE gate: **PR #1739** (Int-W5 Dockerfile hotfix) @ `903adf53cae4`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1739 LIVE confirmed
- [x] **Gate 1:** Focused unit tests green locally (W4 baselines unloosened)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify (migrations + seed v1.1 + refuse paths)
- [ ] **Gate 4:** PROD tip verify (health SHA = tip + Azure success)
- [ ] **Gate 5:** Master conveyor updated after LIVE
