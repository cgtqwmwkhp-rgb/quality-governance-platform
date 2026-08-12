# Change Ledger (CL-STANDARDS-WAVE1-PR-A)

## 1) Summary
- **Feature / Change name:** Standards Governance Wave 1 PR-A — `/compliance` matrix shell.
- **User goal:** One Compliance Standards home: `/standards` redirects into `/compliance` with matrix chrome, full Evidence Workspace slots, and hover preview scaffolding — live graph fills in PR-B.
- **In scope:** Route redirect (query-preserving), nav collapse, StandardsMatrixShell + presets/filters, EvidenceWorkspaceHost + five panel slots (stubs), cell hover preview chrome, i18n, tests.
- **Out of scope:** Live audit/NC/actions/risk/cert joins (PR-B), 5064 alignment_edges (PR-C), EXACT share/SLA (PR-D), Library ingest AI (PR-E), buyer automation (PR-F), Constructionline.
- **Feature flag / kill switch:** None. Revert PR restores dual nav + `/standards` page route.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-A-01 | `/standards` | Separate thin catalogue page | Redirect → `/compliance` (preserves query; `view=matrix`) |
| SG-A-02 | Nav | Dual Standards + ISO Compliance | Single Standards item → `/compliance` |
| SG-A-03 | `/compliance` | Evidence centre only | Matrix \| Evidence mode; matrix chrome + workspace host |
| SG-A-04 | Workspace | Single stacked card / drawer risk | Full workspace tabs: Evidence · Audits & NC · Actions · Risks · Certs (PR-B stubs + deep-links) |
| SG-A-05 | Hover | None | Cell hover preview chrome (stub data until PR-B) |

- **Frontend:** App redirect, Layout nav, ComplianceEvidence host wiring, `pages/compliance/*` shell modules, i18n en/cy, link retargets (IMS, KnowledgeExceptions, builderMapAssistApi).
- **Backend / APIs / DB / migrations:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI shell; existing Evidence mode remains default-reachable.
- **Tolerant reader / strict writer applied?** N/A (no new write APIs).
- **Breaking changes:** `/standards` catalogue route retired (redirect). Deep-links updated.
- **Migration plan:** None.
- **Rollback strategy (DB):** No DB change — revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Dual Compliance entry points | `/standards` + `/compliance` competed; catalogue felt bolt-on | Single `/compliance` survivor; Standards is the programme shell |
| Constructionline | Not in repo; risk of reintroduction | Explicitly excluded from framework presets |
| Scheme shell honesty | UVDB/Planet Mark could appear as ISO clause trees | Matrix quarantines `kind===scheme` from clause catalogue |
| Evidence Workspace | Drawer/stacked panel risk | Full-page workspace with named slots for PR-B live graph |
| Live audit/NC cover gate | Not in shell | Slots + deep-links only; cover gate lands in PR-B |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Navigating `/standards` lands on `/compliance` with query preserved and matrix view available.
- [x] AC-02: Layout shows one Standards nav item pointing at `/compliance` (no duplicate ISO Compliance entry).
- [x] AC-03: Matrix chrome supports framework column filters + presets (core/cyber/people/buyer/all); Constructionline absent.
- [x] AC-04: Selecting a cell opens full Evidence Workspace (not Sheet) with five tab slots and deep-links.
- [x] AC-05: Existing Evidence centre remains reachable via Matrix \| Evidence mode toggle.
- [x] AC-06: Focused vitest coverage for redirect, nav, filters, and link retargets.

## 5) Testing Evidence (link to runs)
- [x] Unit/Vitest (local): standardsMatrixFilters, App redirect, Layout, builderMapAssistApi, IMSDashboard, KnowledgeExceptions, ComplianceEvidence — 86 passed.
- [x] Typecheck: `tsc --noEmit` clean on worktree.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: User opens Standards from nav → `/compliance` matrix shell loads with framework filters/presets.
- [x] CUJ-02: User clicks a matrix cell → full workspace opens with Evidence / Audits & NC / Actions / Risks / Certs tabs and deep-links to existing modules.

## 7) Observability & Ops
- No new telemetry. Support: if matrix looks empty, confirm Evidence mode still works; PR-B supplies live cell aggregate.
- Runbook: tip-chase via conveyor allowlist; DONE only when prod tip sha matches merge.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (STACK_MAX=1 tip-chase).
2. Staging: open `/compliance?view=matrix`, confirm redirect from `/standards`, nav single entry, workspace tabs.
3. Promote PROD; verify `/api/v1/meta/version` build_sha = main tip; smoke same CUJs on prod FQDN.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Nav regression, broken `/compliance` load, or size-limit/index shell failure in prod.
- **Rollback steps:** Revert merge commit; redeploy prior artifacts via governed path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Worktree branch: `feat/standards-wave1-pr-a-shell`
- Shell: `frontend/src/pages/compliance/StandardsMatrixShell.tsx`, `EvidenceWorkspaceHost.tsx`
- Host: `frontend/src/pages/ComplianceEvidence.tsx`
- Ledger: `scripts/governance/pr_body_standards_wave1_pr_a.md`
- Hero board: standards-hero-board.canvas.tsx (PR-A → Alive when opened)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only shell contracts; no migration; PR-B owns live graph
- [x] **Gate 2:** Focused vitest + tsc locally green; hosted CI pending
- [ ] **Gate 3:** Staging verification pending tip-chase
- [x] **Gate 4:** No canary required — additive UI shell
- [x] **Gate 5:** Production verification = tip sha + CUJ-01/02 on prod FQDN
