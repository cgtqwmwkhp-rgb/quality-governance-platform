# Change Ledger (CL-PATH11-CUJ-RISK-FROM-NEAR-MISS)

## File allowlist (exclusive)
- `src/domain/services/near_miss_risk_links.py` (NEW)
- `src/api/routes/near_miss.py` (raise-risk endpoint + imports)
- `src/api/schemas/near_miss.py` (`linked_risk_ids` on response)
- `tests/unit/test_near_miss_risk_links.py` (NEW)
- `frontend/src/api/nearMissesClient.ts`
- `frontend/src/pages/NearMissDetail.tsx`
- `frontend/src/pages/nearMissRiskLinks.ts` (NEW)
- `frontend/src/pages/__tests__/nearMissRiskLinks.test.ts` (NEW)
- `scripts/governance/pr_body_cuj_risk_from_near_miss.md`

**Zero overlap** with notification-standards / investigation-capa / Layout.tsx / kill-404s.

## 1) Summary
- **Feature / Change name:** CUJ — Raise risk from near miss with bidirectional links
- **User goal (1–2 lines):** From near-miss detail, operators can raise a risk register entry that links back to the near miss (`risk_source`) and stores the risk id on `near_miss.linked_risk_ids`.
- **In scope:** `POST /near-misses/{id}/raise-risk`; link helpers; NearMissDetail Raise risk CTA + linked risk deep links; unit/vitest
- **Out of scope:** Layout.tsx; notifications; investigation CAPA; schema migrations (uses existing columns)
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend:** NearMissDetail Raise risk + linked risks panel; nearMissesClient.raiseRisk
- **Backend:** near_miss raise-risk route; near_miss_risk_links helpers; NearMissResponse.linked_risk_ids
- **APIs:** `POST /api/v1/near-misses/{id}/raise-risk`
- **Schemas:** NearMissResponse + RaiseRisk request/response models
- **Database:** None (uses existing `near_misses.linked_risk_ids`, `risks.risk_source`)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + optional response field
- **Tolerant reader / strict writer applied?** Yes — `linked_risk_ids` optional; `risk_source` encoded as `near_miss:{id}|{ref}`
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit; existing linked rows remain harmlessly

## 4) Acceptance Criteria (AC)
- [x] AC-01: Raise risk creates Risk with `risk_source` encoding near_miss id
- [x] AC-02: Near miss `linked_risk_ids` updated idempotently
- [x] AC-03: NearMissDetail exposes Raise risk action and linked risk deep links
- [x] AC-04: Response includes bidirectional hrefs
- [x] AC-05: Unit + Vitest cover link helpers

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_near_miss_risk_links.py`
- [x] Frontend unit — `nearMissRiskLinks.test.ts`
- [ ] Integration — deferred to CI

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Near miss detail → Raise risk → risk register entry created
- [x] **CUJ-02:** Near miss shows linked risk id → deep link to risk register
- [x] **CUJ-03:** Risk.risk_source parseable back to near_miss id

## 7) Observability & Ops
- **Logs:** Audit event `near_miss.risk_raised`
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Raise risk from a staging near miss; confirm both sides linked
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Spot-check one raise-risk + reverse parse

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Bad risk rows / incorrect linkage
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
