# Change Ledger (CL-STANDARDS-WAVE3-PR-F3)

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-F3 — Standards health digests on Monitoring.
- **User goal:** See freshness, ingest backlog, open NC by clause, recurrence rate, and certificate expiry on Compliance Automation (Monitoring) without a second analytics surface.
- **In scope:** `GET /api/v1/compliance-automation/standards-digests` (audit:read); Standards health tab + KPI tiles + SoR deep-links; pure roll-up helpers; unit/vitest coverage; i18n.
- **Out of scope:** Second analytics page; Evidence strip / F1 presets; Constructionline; `/standards` revival; Celery nightly schedulers; loosening auto-confirm (≥98% + EXACT stays).
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-F-05 | Monitoring digests | Invisible | Freshness + ingest backlog + NC recurrence digests |
| SG-F-06 | NC / cert analytics | Invisible | Open NC by clause + recurrence rate + cert expiry board |
| SG-F-05b | Authz | N/A | Route gated on `audit:read` (no debt-list entry) |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive read-only compose of existing SoRs; no schema / alembic.
- **Tolerant reader / strict writer applied?** FE tolerant mapper (`mapStandardsDigest`); backend does not write.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Standards hygiene visibility | Matrix / Exceptions only | Monitoring digests with deep-links |
| Auto-confirm gate | ≥98% + EXACT (PR-E) | Unchanged; digest surfaces the rule only |
| Analytics surface count | Monitoring tabs | Still one Monitoring page (new tab only) |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `GET /api/v1/compliance-automation/standards-digests` returns freshness, ingest backlog, NC-by-clause + recurrence, cert expiry board.
- [x] AC-02: Route gated on `audit:read`; no authz debt-list / ceiling change.
- [x] AC-03: Digest uses bounded queries — no `get_matrix_summary` / per-clause `get_cell` loop.
- [x] AC-04: Empty / zero-denominator states render `—`; no fabricated percentages.
- [x] AC-05: Rows deep-link to matrix cell, Exceptions inbox, Audits findings, cert shelf.
- [x] AC-06: Bare clause tokens are unattributed (never counted into a framework).
- [x] AC-07: Auto-confirm remains ≥0.98 + EXACT; digest does not change gate code.
- [x] AC-08: No new page/route/nav entry beyond Monitoring tab.
- [ ] AC-09: Hosted CI green; STG=PROD tip LIVE after merge.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_digest_service.py`
- [x] Vitest: helpers + `ComplianceAutomation.standardsDigest.test.tsx`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/compliance-automation` → Standards health → see digests / tiles.
- [x] CUJ-02: NC clause → matrix deep-link; backlog clause → Exceptions filter.
- [x] CUJ-03: Empty freshness / null recurrence → `—` (no invented numbers).

## 7) Observability & Ops
- No new backend metric. A `—` means the denominator is genuinely zero / untracked. `scan_truncated` is returned when scan caps are hit.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after CI green (STACK_MAX tip-chase).
2. Staging: open Monitoring → Standards health; confirm digests + deep-links.
3. Promote PROD; verify health tip = main tip.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Digest numbers disagree with matrix/Exceptions, or endpoint is slow.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/standards-wave3-pr-f3-digests`
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_f3.md`
- Parent LIVE: #1735 @ `449a4952ac0f`
- Spec: SG-F-05 / SG-F-06 on standards-hero-board

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [ ] **Gate 1:** Focused unit/vitest green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Hero board / mission / allowlist updated after LIVE
