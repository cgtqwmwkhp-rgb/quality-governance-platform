# Change Ledger (CL-WC-W1-ACTIONS-PERMALINK-CALLSITE-SWEEP)

## 1) Summary
- **Feature / Change name:** Follow-up to D-W1-04 (#967) — migrate remaining FE call sites from legacy `/actions/item?key=` to RESTful `/actions/:id` permalinks
- **User goal (1-2 lines):** Audit finding CAPA links and compliance automation watch-action links open action detail via canonical permalink URLs, consistent with Actions hub and portal.
- **In scope:** `Audits.tsx`, `ComplianceAutomation.tsx`; reuse `buildActionDetailPath` from `actionLinks.tsx` (on `main` via #967 / `87cba539`)
- **Out of scope:** `Actions.tsx`, `ActionDetail.tsx`, `App.tsx`, Layout nav, portal (delivered in #967); e2e specs; backend
- **Dependency:** #967 merged to `main` (`87cba539`); this PR is rebased on `origin/main`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Audits.tsx` (finding loop “Open CAPA detail” navigation); `ComplianceAutomation.tsx` (regulatory watch action links)
- **Backend:** None
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Call-site only — legacy `/actions/item?key=` redirect from #967 still handles old bookmarks
- **Breaking changes:** None
- **Rollback strategy:** Revert this commit; no data impact

## 4) Acceptance Criteria (AC)
- [x] AC-01: Audits finding loop navigates to `/actions/:id` via `buildActionDetailPath`
- [x] AC-02: ComplianceAutomation watch-action links use `buildActionDetailPath`
- [x] AC-03: No remaining hardcoded `/actions/item?key=` in allowlisted pages (excluding #967-owned files)

## 5) Testing Evidence
- [ ] CI — linked after rebase onto `main`
- [ ] `cd frontend && npm test -- Audits.findings-closure` (regression on findings loop)

## 6) Critical Journeys Verified (CUJ)
- [ ] CUJ-01: Audits → finding with linked CAPA → Open CAPA detail → `/actions/capa%3A{id}`
- [ ] CUJ-02: Compliance Automation → regulatory watch impact with action → link opens permalink

## 7) Release Plan
1. Squash-merge this PR to `main` after CI green
2. Staging verification per platform release playbook

## 8) Rollback Plan
1. Revert squash commit on main
2. Redeploy previous known-good SHA

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete

## Test plan
- [ ] `cd frontend && npm test -- Audits.findings-closure`
- [ ] Manual: Audits findings view → Open CAPA detail lands on `/actions/capa%3A…`
- [ ] Manual: Compliance Automation → watch action link uses `/actions/:id`

## Stack note
Previously stacked on `feat/wc-w1-actions-permalinks` (#967). Rebased onto `main` after #967 merged; base branch is `main`.
