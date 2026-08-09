# Change Ledger (CL-CS-SCHEDULE-OWNER-DISPLAY-NAME)

## 1) Summary
- **Feature / Change name:** Compliance Schedule — show owner display name
- **User goal (1–2 lines):** Schedule list/detail/edit hint show the person's name (e.g. "Jamie Uncle") instead of the Wave-1 id-only fallback "Owned by someone else".
- **In scope:** Additive `owner_name` on schedule `RequirementResponse`; batch resolve via `User.full_name` in `compliance_schedule` routes; FE display helper + list/detail/form hint; FE + lightweight BE unit tests.
- **Out of scope:** `src/api/routes/compliance.py` / WI-1 CEL; owner picker UX redesign; migrations; notification copy.
- **Feature flag / kill switch:** None — additive response field; FE falls back honestly when name absent.

## 2) Impact Map (what changed)
- **Frontend:** `complianceScheduleClient.ts` type; `formatOwnershipLabel` + `useOwnershipLabel`; `ComplianceSchedule.tsx`, `ComplianceScheduleDetail.tsx`, `RequirementFormDialog.tsx`; owner/helpers tests; `en.json` `you_named` key.
- **Backend:** `RequirementResponse.owner_name`; `_resolve_owner_names` batch helper; list + single-item serialize paths in `compliance_schedule.py`.
- **APIs:** Additive optional `owner_name` on requirement responses (list/get/create/update/activate/deactivate/FRA confirm).
- **Schemas/contracts:** `src/api/schemas/compliance_schedule.py` — optional field only.
- **Database:** None.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.
- **Tests:** `tests/unit/test_compliance_schedule_owner_name_response.py`; FE owner + helpers tests.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive optional response field; tolerant FE reader keeps Wave-1 fallbacks when `owner_name` absent.
- **Tolerant reader / strict writer applied?** Yes.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** No DB change — revert deploy/commit only.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Schedule owner identity in UI | `owner_id` vs current user only → "Owned by someone else" | Resolves active in-tenant `User.full_name` as `owner_name` |
| Unassigned honesty | "Unassigned" | Unchanged |
| Soft-deleted / inactive owner | N/A (name never shown) | Name omitted; FE keeps honest fallback |
| WI-1 CEL / `compliance.py` | Untouched | Still untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `RequirementResponse` includes optional `owner_name` near `owner_id`.
- [x] AC-02: List endpoint batch-loads names for the page (no N+1); single-item paths populate when `owner_id` set.
- [x] AC-03: FE shows name for other owners; `"${name} (you)"` when you; Wave-1 fallbacks when name absent.
- [x] AC-04: No changes to `src/api/routes/compliance.py` / WI-1 CEL.

## 5) Testing Evidence
- [x] Backend unit — `pytest tests/unit/test_compliance_schedule_owner_name_response.py` (+ FRA eligible response suite) — 7 passed
- [x] Frontend — vitest `ComplianceSchedule.owner.test.tsx` + `complianceScheduleHelpers.test.ts` — 22 passed
- [ ] Full CI on PR

## 6) Critical Journeys
- [x] CUJ-01: Open Compliance Schedule list → other owner's row shows resolved name when API returns `owner_name`.
- [x] CUJ-02: Your own obligation with `owner_name` shows `"Name (you)"`; without name still "Owned by you".
- [x] CUJ-03: Unassigned still shows "Unassigned"; missing `owner_name` still "Owned by someone else".

## 7) Observability & Ops
- No new metrics/alerts. Failures to resolve a user silently omit `owner_name` (FE fallback). No runbook change.

## 8) Release Plan
1. Merge after CI green (do not tip-chase from this PR authoring step).
2. Main CI → Azure deploy → verify ACA tip SHA + health.
3. Spot-check schedule list: assigned other user shows full name.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Wrong names shown, or schedule list/detail regressions.
- **Rollback steps:** Revert the merge commit on `main` and redeploy previous tip; no DB unwind.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack
- Unit: `tests/unit/test_compliance_schedule_owner_name_response.py`
- FE: `frontend/src/pages/__tests__/ComplianceSchedule.owner.test.tsx`
- Change Ledger: this body

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger (schedule display only; no WI-1)
- [x] **Gate 1:** Additive API/UX contract (`owner_name` optional)
- [ ] **Gate 2:** CI green on the PR
- [ ] **Gate 3:** Staging verification (after merge/deploy)
- [x] **Gate 4:** Canary N/A — small display fix
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed at open
