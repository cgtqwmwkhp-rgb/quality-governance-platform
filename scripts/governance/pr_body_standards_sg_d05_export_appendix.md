# Change Ledger (CL-STANDARDS-SG-D05-EXPORT-APPENDIX)

> **Start gate:** SG-D-04 (#1748) LIVE — tip `1fafec32e159`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards SG-D-05 — Audit pack appendix (evidence · findings · actions · certs).
- **User goal:** Download one audit pack from `/compliance` that includes SoR pointers for the active Evidence theme filter, unlocking LIVE-07.
- **In scope:** Additive `standards_appendix` on `GET /api/v1/compliance/audit-pack`; filter by matrix framework ids; pointers only (id, title, status, path). Honest unattributed / unmatched / other-framework counts. Pass current Evidence preset from the Audit Pack button.
- **Out of scope:** Cell-aggregate fork; second blob library; Alembic; new notifier; Entra flag; TrapGuard/ingest; inventing EXACT for CHAS/SSIP/PM/UVDB; flipping `covers_framework` from catalogues.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-D-05-01 | `GET /api/v1/compliance/audit-pack` | ISO CEL pack only | + `standards_appendix` with evidence / findings / actions / certs pointers |
| SG-D-05-02 | Theme filter | Pack ignored Evidence preset | Repeatable `frameworks=` query; empty = full programme (Constructionline out) |
| SG-D-05-03 | Cert honesty | N/A in pack | PAT/insurance `proof_scope: unmatched`; never counted as ISO proof |
| SG-D-05-04 | Bare clause tokens | N/A | Unattributed, not painted as 9001 |

## 3) Compatibility & Data Safety
- Additive JSON key. Existing CEL provenance unchanged (`pack_version` stays `gkb-wl1-1.0`).
- Read-only SoR scans with the same 2000-row cap as Monitoring digests. Truncation is flagged.
- **Rollback strategy:** Revert merge and redeploy prior tip `1fafec32e159`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| SoR | Audits / Actions / CEL / cert shelf | Unchanged SoR; appendix is pointers |
| Cell-aggregate | Workspace/matrix only | Untouched — appendix does not call `get_cell` / `get_matrix` |
| Cover / EXACT / catalogues | Unchanged | Unchanged |
| Entra MFA attestation | Flag default false | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Pack JSON includes `standards_appendix` with evidence, findings, actions, certs.
- [x] AC-02: `14001-6.1.2` does not appear under a 9001-only filter; bare `7.5` is unattributed.
- [x] AC-03: PAT / insurance register certs are `unmatched`, never 9001 proof.
- [x] AC-04: Evidence Audit Pack button sends the active preset framework ids.
- [x] AC-05: No Alembic; no cell-aggregate fork; TrapGuard/ingest/`covers_framework`/Entra untouched.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_export_appendix.py`
- [x] Integration: `tests/integration/test_audit_pack_export.py` (appendix key + CEL honesty)
- [x] FE: `frontend/src/pages/__tests__/ComplianceEvidence.test.tsx` (PX-252 + frameworks)
- [x] FE: `frontend/src/api/client.test.ts` (repeatable `frameworks=` query)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator on Evidence preset All downloads Audit Pack → appendix frameworks include ISO + buyer schemes; unmatched certs listed separately.
- [x] CUJ-02: Operator on ISO-only filter does not receive PAT as ISO proof or 14001 findings as 9001 rows.

## 7) Observability & Ops
- Header `X-Standards-Appendix-Version: sg-d05-1.0`.
- Truncation flags on each appendix section when the scan or row cap is hit.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `1fafec32e159` (`STACK_MAX=1`).
2. Focused unit/integration/Vitest green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Appendix invents coverage; paints PAT as ISO; forks cell-aggregate; TrapGuard/ingest change; Entra flag flipped.
- **Rollback steps:** Revert merge; redeploy prior tip `1fafec32e159` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_sg_d05_export_appendix.md`
- Parent LIVE gate: **PR #1748** (SG-D-04) @ `1fafec32e159`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1748 LIVE confirmed
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
