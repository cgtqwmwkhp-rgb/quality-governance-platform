# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Controlled google-genai 2.x constraint alignment
- **User goal (1-2 lines):** Make `requirements.txt` honestly declare the google-genai 2.x major already used in production lock, and prevent silent 1.x downgrades.
- **In scope:** Raise floor to `google-genai>=2.14.0,<3.0.0`; add regression unit guards for constraint/lock/import surface. Supersedes Dependabot #880.
- **Out of scope:** Redis 8, frontend majors, Storybook/Vite majors, API behavior changes.
- **Feature flag / kill switch:** Existing `USE_GOOGLE_GENAI=0` remains.

## 2) Impact Map (what changed)
- **Frontend:** None.
- **Backend:** None (constraint + tests only; call sites already use google-genai GA imports).
- **APIs / Schemas / Database:** None.
- **Workflows:** None.
- **Dependencies:** `requirements.txt` floor/ceiling only. `requirements.lock` already pins `google-genai==2.14.0` — no lock churn expected.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Align declared constraint with already-deployed lock pin. No runtime code change.
- **Breaking changes:** Fresh `pip install -r requirements.txt` without lock will no longer accept 1.x.
- **Migration plan:** Merge; normal deploy uses lock.
- **Rollback strategy:** Revert constraint commit if a environment installs without lock and fails.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `requirements.txt` requires google-genai 2.14+ and blocks 3.x.
- [x] AC-02: Lock remains on google-genai 2.x.
- [x] AC-03: Gemini service modules keep `google.genai` import surface + kill switch.
- [x] AC-04: Supersedes Dependabot #880.

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_google_genai_major_floor.py`.
- [ ] Full CI — this PR checks tab.
- [x] Contract/E2E — N/A (constraint-only).

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Constraint/lock declare google-genai 2.x.
- [x] CUJ-02: Gemini AI/review services still reference google-genai SDK imports and kill switch.

## 7) Observability & Ops
- **Logs/Metrics/Alerts:** No change.
- **Runbook updates:** Note USE_GOOGLE_GENAI kill switch unchanged.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** After deploy, hit a Gemini-backed path (or confirm AI stub path when key absent) + `/health`.
- **Canary/Prod:** Normal promotion; no schema/migration.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Gemini import/runtime failures after environments that ignore the lock.
- **Rollback steps:** Redeploy prior SHA / restore `google-genai>=1.0.0` constraint if required.
- **Owner:** Platform team.

## 10) Evidence Pack (links)
- CI run(s): This PR checks tab.
- Staging deploy evidence: After promotion.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
