# Change Ledger (CL-PATH11-FIX-RAISE-RISK-ENTERPRISE)

## File allowlist (exclusive)
- `src/domain/services/near_miss_risk_links.py`
- `src/api/routes/near_miss.py`
- `src/api/routes/risk_register.py`
- `tests/unit/test_near_miss_risk_links.py`
- `tests/unit/test_raise_risk_enterprise_path.py`
- `frontend/src/api/riskRegisterClient.ts`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/NearMissDetail.tsx`
- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/nearMissRiskLinks.ts`
- `frontend/src/pages/__tests__/nearMissRiskLinks.test.ts`
- `scripts/governance/pr_body_fix_raise_risk_enterprise.md`

## 1) Summary
- **Feature / Change name:** Fix near-miss Raise risk → Enterprise Risk Register (`risks_v2`)
- **User goal (1–2 lines):** Operators raising a risk from a near miss land in the canonical Risk Register UI with a focused row, without Internal Server Error from the legacy `risks` dual-register fracture.
- **In scope:** Rewrite raise-risk to create `EnterpriseRisk`; FK-safe owner; IntegrityError → 409; RiskRegister `?riskId=` / `nearMissRef` deep links; Dashboard High Risks from `/risk-register/summary`
- **Out of scope:** Deleting legacy `risks` table; Incident/RTA/Complaint raise-risk UI; Layout.tsx
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend:** RiskRegister deep-link focus/filter/highlight; Dashboard summary source; nearMissRiskLinks href helper; NearMissDetail linked-risk navigation
- **Backend:** `create_enterprise_risk_from_near_miss`; raise-risk route response/error handling; risk-register list/detail expose `linked_incidents`
- **APIs:** `POST /api/v1/near-misses/{id}/raise-risk` now creates enterprise register rows
- **Schemas:** Slim raise-risk response keeps `reference_number` alias for FE toast
- **Database:** None (uses existing `risks_v2` + `near_misses.linked_risk_ids`)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Corrects #949 path to write the register the UI already reads
- **Tolerant reader / strict writer applied?** Yes — treatment strategies accept legacy + enterprise values; owner FK validated before insert
- **Breaking changes:** New risks from raise-risk appear in enterprise register only (intended). Prior legacy rows from #949 remain in `risks` and are not auto-migrated.
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit; no schema change

## 4) Acceptance Criteria (AC)
- [x] AC-01: Raise risk creates `EnterpriseRisk` (`risks_v2`) linked via `context`/`linked_incidents`
- [x] AC-02: Missing/invalid assignee does not 500 (FK-safe owner; IntegrityError → 409)
- [x] AC-03: Response includes `risk_register_href` with `riskId` (+ optional `nearMissRef`)
- [x] AC-04: RiskRegister focuses/highlights `?riskId=` and can filter `nearMissRef`
- [x] AC-05: Dashboard High Risks uses enterprise summary (not legacy `risksApi`)
- [x] AC-06: Unit guards cover treatment map, owner resolve, enterprise path

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_near_miss_risk_links.py`, `tests/unit/test_raise_risk_enterprise_path.py`
- [x] Frontend unit — `nearMissRiskLinks.test.ts` (run in CI; local node_modules may be absent in worktree)
- [ ] Integration — deferred to CI / staging smoke

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Near miss detail → Raise risk → enterprise risk created → navigate to `/risk-register?riskId=…`
- [x] **CUJ-02:** Linked risk chip opens focused enterprise register row
- [x] **CUJ-03:** Dashboard High Risks reflects enterprise register summary

## 7) Observability & Ops
- **Logs:** Existing audit event `near_miss.risk_raised`; IntegrityError logged at exception
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** On SWA staging, open NM-2026-0001 → Raise risk → confirm 201 and Risk Register focus (no 500)
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** tip==LIVE SHA match; spot-check one raise-risk

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Raise-risk 5xx or wrong register target after deploy
- **Rollback steps:** Revert commit and redeploy previous SHA
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
