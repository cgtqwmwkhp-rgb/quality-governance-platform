# Change Ledger (CL-STANDARDS-WAVE1-PR-B)

## 1) Summary
- **Feature / Change name:** Standards Governance Wave 1 PR-B — live audit/NC/action/risk/cert graph.
- **User goal:** Matrix cells and Evidence Workspace panels reflect live SoR joins (internal + mock + imported findings, CAPA/actions, risks, cert shelf, evidence links) with an honest cover gate.
- **In scope:** Cell aggregate read-model/API; fill AuditsNc/Actions/Risks/Certs/(Evidence) panels; open NC/action blocks covered; recurrence red-flag; prior-outcome upload CTA → existing import path; cert shelf proof links; mock `kind=mock` honesty; LIVE-01…06 / LIVE-08 behaviour where feasible.
- **Out of scope:** 5064 `alignment_edges` (PR-C), EXACT share/SLA (PR-D), Library ingest AI (PR-E), buyer automation (PR-F), Constructionline.
- **Feature flag / kill switch:** None. Revert restores PR-A stub panels + stub cell verdicts.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-B-01 | API | No cell join | `GET /api/v1/compliance/cell-aggregate` + `/matrix` read-model |
| SG-B-02/03 | Audits | Stub panel | Live findings; mock labelled; gaps still paint |
| SG-B-04 | Import UX | None in workspace | CTA → `/audits?modal=import` (existing UVDB/external pipelines) |
| SG-B-05/07 | Cover gate | Stub hash verdicts | Open NC / open action → never `covered` |
| SG-B-06 | Recurrence | None | Red-flag when NC repeats after close |
| SG-B-08 | Risks | Stub | Linked operational/enterprise risks + 6.1.x trap note |
| SG-B-09 | Certs | Stub | AssuranceCertShelf items as framework/clause proof |
| SG-B-10 | Workspace panels | PR-A stubs | Live extracted panels (shared aggregate fetch) |
| LIVE-08 | SoR | — | Explicit read-model only; no second Standards DB |

- **Frontend:** `pages/compliance/workspace/*`, matrix shell live paint, hover preview, client + types, focused vitest.
- **Backend / APIs / DB / migrations:** New service + compliance routes only. **No Alembic.**

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive read APIs; existing SoR write paths unchanged.
- **Tolerant reader / strict writer applied?** Read-model joins tolerant clause tokens (`7.5`, `9001-7.5`).
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** No DB change — revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Matrix honesty | Hash stub verdicts | Live join with cover gate |
| Open NC / CAPA | Could appear covered in stub | Blocked from `covered` |
| Recurrence | Invisible | Red-flag after close→repeat |
| Mock audits | Undifferentiated | Honest `Mock audit` label; still paints gaps |
| Prior outcomes | Evidence centre only | Workspace CTA into existing import SoR |
| Cert proof | Stub | Cert shelf scheme→framework proof edges |
| Second Standards DB | Risk of bolt-on | Forbidden — LIVE-08 read-model only |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Cell aggregate API returns findings/actions/risks/certs/evidence/imported priors for framework+clause.
- [x] AC-02: Open NC or open action → `cover_blocked` and verdict ≠ `covered`.
- [x] AC-03: Recurrence red-flag when NC reopens after prior close on same clause.
- [x] AC-04: Workspace panels render live lists + deep-links; prior upload CTA uses existing import modal path.
- [x] AC-05: Mock findings labelled; matrix/hover show live (or degraded unknown) not PR-A stub chrome when healthy.
- [x] AC-06: Focused unit + vitest coverage for cover gate / panels.
- [ ] AC-07: Hosted CI green; STG LIVE-01…06 / LIVE-08 tip verify after merge (SG-B-11).

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_standards_cell_aggregate_service.py`
- [x] Vitest (local): `standardsWorkspaceLivePanels` (+ existing matrix filter suite)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: User opens Standards matrix → cells fetch live aggregate summary; open NC/action cannot show Covered.
- [x] CUJ-02: User opens clause workspace → Audits & NC / Actions / Risks / Certs / Evidence panels show joined SoR data; prior-outcome upload deep-links to `/audits?modal=import`.

## 7) Observability & Ops
- No new telemetry. Support: if matrix shows “Live graph unavailable”, Evidence centre and SoR modules still work; check `/api/v1/compliance/cell-aggregate`.
- Runbook: tip-chase via conveyor allowlist; DONE only when prod tip sha matches merge + LIVE checks.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (STACK_MAX tip-chase).
2. Staging: `/compliance?view=matrix` — open cell with NC/action; confirm cover block + panels; import CTA.
3. Promote PROD; verify `/api/v1/meta/version` build_sha = main tip; smoke CUJ-01/02 + LIVE-01…06/08 on prod FQDN.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Matrix/workspace 500s, false-green covered cells with open NC, or import CTA broken.
- **Rollback steps:** Revert merge commit; redeploy prior artifacts via governed path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Worktree branch: `feat/standards-wave1-pr-b-live-graph`
- Service: `src/domain/services/standards_cell_aggregate_service.py`
- Routes: `src/api/routes/compliance.py` (`/cell-aggregate`, `/cell-aggregate/matrix`)
- Panels: `frontend/src/pages/compliance/workspace/*`
- Ledger: `scripts/governance/pr_body_standards_wave1_pr_b.md`
- Hero board: standards-hero-board.canvas.tsx (PR-B → Alive when opened)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** No migration; reuses audits/imports/actions/risks/cert shelf SoR; PR-C/D/E excluded
- [x] **Gate 2:** Focused unit + vitest locally; hosted CI pending
- [ ] **Gate 3:** Staging verification pending tip-chase (LIVE-01…06, LIVE-08)
- [x] **Gate 4:** No canary required — additive read-model + UI panels
- [x] **Gate 5:** Production verification = tip sha + CUJ-01/02 + LIVE checks on prod FQDN
