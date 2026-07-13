# Change Ledger (CL-PATH11-CUJ-INVESTIGATION-CAPA-FROM-NEAR-MISS)

## File allowlist (exclusive)
- `frontend/src/components/investigations/handoffLinks.ts`
- `frontend/src/components/investigations/handoffLinks.test.ts`
- `frontend/src/pages/NearMissDetail.tsx`
- `frontend/src/pages/__tests__/NearMissDetail.test.tsx` (NEW)
- `frontend/src/pages/InvestigationDetail.tsx`
- `scripts/governance/pr_body_cuj_investigation_capa_from_near_miss.md`

**Zero overlap** with raise-risk CTA / notification-standards / Layout.tsx / kill-404s.

## 1) Summary
- **Feature / Change name:** CUJ — Near miss → Investigation → CAPA residual honesty + deep links
- **User goal (1–2 lines):** Creating an investigation from a near miss deep-links into the investigation; CAPA counts never pretend to be zero when the load failed; investigation list rows are navigable with status.
- **In scope:** NearMissDetail investigation deep links + CAPA handoff honesty; InvestigationDetail CAPA count honesty; shared `formatCapaActionsCount`; Vitest
- **Out of scope:** Raise risk; standards notifications; Layout.tsx; schema/migrations
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend:** NearMissDetail, InvestigationDetail, handoffLinks helpers + tests
- **Backend:** None
- **APIs:** None (consumes existing from-record + actions list)
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX honesty
- **Tolerant reader / strict writer applied?** Yes — unavailable → `—`, not `0`
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Investigation rows on near-miss detail deep-link to `/investigations/:id` and show status
- [x] AC-02: Create investigation navigates to the new investigation detail
- [x] AC-03: Near-miss CAPA count uses `—` when actions load fails (never faux empty)
- [x] AC-04: InvestigationDetail CAPA proof count uses `—` + unavailable message on load failure
- [x] AC-05: Vitest covers deep link + CAPA honesty paths

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — handoffLinks + NearMissDetail tests
- [ ] E2E — deferred to CI / staging

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Near miss → Create Investigation → lands on investigation detail
- [x] **CUJ-02:** Near miss → open linked investigation → CAPA handoff deep link
- [x] **CUJ-03:** CAPA list failure → `—` not `0` on near miss and investigation

## 7) Observability & Ops
- **Logs:** Existing trackError + toast on CAPA load failure
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Create investigation from near miss; force CAPA failure (or mock) and confirm honesty
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Spot-check near miss → investigation → CAPA CTA

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Broken navigation / false CAPA empty states
- **Rollback steps:** Revert commit and redeploy
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: pending
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
