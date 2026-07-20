# Change Ledger (CL-PORTAL-WORK-COLLAPSE)

## 1) Summary
- **Feature / Change name:** Collapsible My Work sections (Employee Portal)
- **User goal (1–2 lines):** Let employees collapse/expand Assigned actions, Training compliance, Pending reading, and Workforce profile so a long action list does not bury training and reading.
- **In scope:** Collapsible section headers with count badges; auto-collapse Assigned actions when there are 4+ items (still expandable)
- **Out of scope:** Reordering sections; filtering/paging actions; Admin Training Matrix changes
- **Feature flag / kill switch:** N/A — UI-only

## 2) Impact Map (what changed)
- **Frontend:** `pages/PortalWork.tsx` — `WorkSection` disclosure headers; `PortalWork.test.tsx` coverage for long-list auto-collapse
- **Backend / APIs / DB:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI only; section content unchanged when expanded
- **Breaking changes:** None
- **Migration / Rollback:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Each My Work section has an Expand/Collapse control with `aria-expanded`
- [x] AC-02: Assigned actions with 4+ items auto-collapses after load (count badge remains visible)
- [x] AC-03: User can re-expand Assigned actions and see the full list
- [x] AC-04: Training / Reading / Profile remain independently collapsible

## 5) Testing Evidence (link to runs)
- [x] Unit — PortalWork collapse test added
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Employee with many assigned actions lands on My Work, sees collapsed Actions with count, expands Training without scrolling through the full action list
- [x] CUJ-02: Employee expands Assigned actions to work a CAPA, then collapses again

## 7) Observability & Ops
- None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Normal merge deploy; hard-refresh `/portal/work`

## 9) Rollback Plan (Mandatory)
- **Trigger:** Collapse state confuses users or hides urgent content unexpectedly
- **Steps:** Revert PR
- **Owner:** Platform / Portal

## 10) Evidence Pack (links)
- CI: linked after open

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Design locked (disclosure headers + auto-collapse long actions)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** N/A
- [x] **Gate 5:** Rollback ready
