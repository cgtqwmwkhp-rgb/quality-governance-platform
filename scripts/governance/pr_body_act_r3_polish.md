# Change Ledger (CL-ACT-R3-POLISH)

## File allowlist (exclusive)

- `frontend/src/pages/Actions.tsx`
- `frontend/src/pages/__tests__/Actions.test.tsx`
- `frontend/src/i18n/locales/en.json` (minimal `actions.*` CUJ keys)
- `scripts/governance/pr_body_act_r3_polish.md`

**Zero overlap** with parallel lanes: Layout/App/client spines; CA-W1b; COPILOT-PG (parked).

## 1) Summary

- **Feature / Change name:** Path11 — Actions Round 3 polish (ACT-R3)
- **User goal:** Honest create→assign→complete CUJ on the list surface; consolidated upstream source links; downstream finding-loop guidance when CAPA is complete.
- **In scope:** `Actions.tsx` assignee honesty, upstream link consolidation, create-dialog next steps, expanded-row completion metadata + finding-loop CTA; vitest proofs; minimal i18n; Change Ledger
- **Out of scope:** Layout/App/client.ts spines; ActionDetail.tsx (already has profile-level assign/complete); backend APIs
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Row assignee | Owner email only when present; silent when unassigned | Always shows assignee (`assigned_to_email` → `owner_email`) or italic **Unassigned** |
| Upstream links | Inline incident/investigation/finding buttons only | Shared `getActionSourceLink` + complaint helper → RTA, near miss, capa_incident, complaint routes |
| Expanded detail | Type + created only | Assignee, completed date, finding-loop CTA for terminal audit-finding CAPA |
| Create dialog | Success implied full workflow done | Footer + success copy state assign/complete happen on profile |
| Email banner test | Skipped (flaky) | Stable `data-testid` assertion re-enabled |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UI copy and links; no API/schema changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Rows without assignee show honest **Unassigned** (not blank owner)
- [x] AC-02: `assigned_to_email` preferred over `owner_email` in list metadata
- [x] AC-03: Upstream links use shared resolver — RTA/near miss/complaint routes render when source id > 0
- [x] AC-04: Expanded completed audit-finding rows show finding-loop CTA linking back to Audits findings console
- [x] AC-05: Create dialog + success state explain assign/complete happen on action profile
- [x] AC-06: Vitest `Actions Round 3 polish` describe block covers CUJ honesty + upstream links

## 5) Testing Evidence

- [x] Vitest `Actions.test.tsx` — `Actions Round 3 polish — CUJ honesty & upstream links` (6 cases) + re-enabled email banner test
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Create action → dialog states assign/complete on profile → success next-steps copy
- [x] CUJ-02: List row with no assignee → **Unassigned** visible in row + expanded panel
- [x] CUJ-03: Complete audit-finding CAPA → expand row → Return to finding loop deep-link
- [x] CUJ-04: Filter `/actions?sourceType=complaint&sourceId=12` → complaint playbook + upstream link honesty

## 7) Observability & Ops

- **Test hooks:** `actions-row-assignee-*`, `actions-source-link-*`, `actions-finding-loop-*`, `actions-create-next-steps`, `actions-complaint-playbook`, `actions-detail-assignee-*`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: create action, verify unassigned label, expand completed finding CAPA

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA (`a598e760`)

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Serial tip LIVE after Azure settles (post #1053)
- [ ] **Gate 5:** Tracker ACT-R3 → done after merge + smoke
