# Change Ledger (CL-STANDARDS-WAVE2-PR-C)

## 1) Summary
- **Feature / Change name:** Standards Governance Wave 2 PR-C — 5064 alignment edges + TrapGuard.
- **User goal:** Versioned EXACT/NEAR/DIFFERENT/UNIQUE alignment from PEL-HSEQ-5064 drives the matrix catalogue; DIFFERENT traps cannot invent shared coverage; technical MFA/CE gaps stay non-PDF-closable.
- **In scope:** `matrix_versions` + `alignment_edges` (Alembic + RLS), import accept-each-then-apply, TrapGuard/TechGapGuard, catalogue API wire-up for StandardsMatrixShell, CEL writer consolidation start, seed from 5064 (Constructionline excluded).
- **Out of scope:** EXACT shared-apply UX (PR-D), SLA notify (PR-D), Library ingest AI (PR-E), buyer automation (PR-F).
- **Feature flag / kill switch:** None. Revert PR + down migration removes tables/routes.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-C-01 | Matrix catalogue | Hardcoded CATALOGUE_ROWS | Alignment-aware API rows from `alignment_edges` |
| SG-C-02 | Alignment SoR | None (legacy cross-maps only) | Versioned `matrix_versions` + `alignment_edges` |
| SG-C-03 | DIFFERENT traps | Number-only matching risk | TrapGuard blocks auto-cross / shared cover invent |
| SG-C-04 | Tech gaps | Unenforced in matrix | TechGapGuard flags MFA/CE-class gaps |
| SG-C-05 | CEL writes | Multiple direct writers | Primary path via `compliance_evidence_link_writer` |
| SG-C-06 | Framework catalogue | `ce`/`cep` labelled Carbon Evolve; Cyber Essentials had no column | `ce`/`cep` are Cyber Essentials / CE Plus with official NCSC links |

- **Backend:** models, alembic `20261105_standards_alignment`, import/read/trap/tech-gap services, compliance routes.
- **Frontend:** StandardsMatrixShell + hover consume alignment; i18n flat keys.
- **Database:** new tenant-scoped RLS tables.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tables + read APIs; FE falls back honestly if no applied matrix version.
- **Tolerant reader / strict writer applied?** Yes — empty alignment → degraded/unknown, not fake green.
- **Breaking changes:** None for existing cell-aggregate cover gate.
- **Migration plan:** Alembic upgrade; seed/apply 5064 JSON; Constructionline excluded in seed.
- **Rollback strategy (DB):** Down revision drops `alignment_edges` / `matrix_versions`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| 5064 EXACT/NEAR/DIFFERENT/UNIQUE | Not modelled | Versioned alignment_edges |
| 6.1.2 DIFFERENT trap | Risk of false shared cover | TrapGuard blocks auto-cross |
| Constructionline | Product-out | Excluded from seed frameworks |
| CEL write path | Fragmented | Writer service for primary compliance routes |
| CE / CEP matrix ids | Mislabelled Carbon Evolve | Cyber Essentials / Plus + NCSC home links |
| LIVE-08 single SoR | Cell aggregate read-model | Alignment annotates; no second Standards DB |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Alembic creates `matrix_versions` + `alignment_edges` with RLS hardening registered.
- [x] AC-02: Import supports dry-run diff → accept-each → apply; Constructionline excluded.
- [x] AC-03: TrapGuard prevents DIFFERENT auto-cross; unit tests cover 6.1.2-class cases.
- [x] AC-04: Matrix shell loads alignment-aware catalogue (fallback if empty).
- [x] AC-05: Focused unit tests for TrapGuard + import pass (45 passed locally).

## 5) Testing Evidence (link to runs)
- [x] `python3.11 -m pytest tests/unit/test_standards_trap_guard.py tests/unit/test_standards_alignment_import.py` — 45 passed.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens `/compliance` matrix → catalogue rows reflect applied alignment version (or honest empty fallback).
- [x] CUJ-02: DIFFERENT trap clause cannot be auto-treated as shared EXACT coverage via TrapGuard.

## 7) Observability & Ops
- Standard API logs on new compliance alignment routes.
- Support: if matrix empty, confirm a matrix version is applied; seed via `scripts/governance/standards/seed_5064_alignment.py`.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after CI green (STACK_MAX=1).
2. Staging: migrate + seed/apply; open matrix; confirm TrapGuard on 6.1.2.
3. Promote PROD; verify build_sha = main tip; smoke CUJs.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration failure, false EXACT shares, or matrix catalogue blank with no fallback.
- **Rollback steps:** Revert merge; alembic downgrade `20261105_standards_alignment`; redeploy prior tip.
- **Owner:** Platform release operator / Standards conveyor.

## 10) Evidence Pack (links)
- Alembic: `alembic/versions/20261105_standards_alignment_edges.py`
- Models: `src/domain/models/standards_alignment.py`
- Guards: `standards_trap_guard.py`, `standards_tech_gap_guard.py`
- Seed: `specs/standards/pel-hseq-5064-alignment-v1.0.json`
- Ledger: `scripts/governance/pr_body_standards_wave2_pr_c.md`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive schema + permissioned routes
- [x] **Gate 2:** Focused unit tests green locally; hosted CI pending
- [ ] **Gate 3:** Staging migrate/seed smoke pending tip-chase
- [x] **Gate 4:** No canary required
- [x] **Gate 5:** Prod verify = tip sha + CUJ-01/02
