# Change Ledger (CL-WC-W1-INCIDENT-ENTERPRISE-RISK / D-W1-09)

## File allowlist (exclusive)
- `src/domain/services/incident_risk_links.py` (NEW)
- `src/api/routes/incidents.py` (raise-risk endpoint + `IncidentResponseWithLinks`)
- `tests/unit/test_incident_risk_links.py` (NEW)
- `frontend/src/api/incidentsClient.ts`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/incidentRiskLinks.ts` (NEW)
- `scripts/governance/pr_body_wc_w1_incident_enterprise_risk.md`

**Zero overlap** with near_miss.py / NearMissDetail (#964), Layout.tsx, Actions permalinks, list URL sync pages, RiskRegister.tsx.

## 1) Summary
- **Feature / Change name:** D-W1-09 — Raise EnterpriseRisk from high/critical incident (P0-INT-3)
- **User goal (1–2 lines):** From incident detail, operators on high/critical incidents can raise an enterprise risk register entry (`risks_v2`) bidirectionally linked via `incident.linked_risk_ids` and `EnterpriseRisk.linked_incidents` / `context`.
- **In scope:** `POST /incidents/{id}/raise-risk`; incident-specific link helpers (separate module from `near_miss_risk_links.py`); IncidentDetail Raise risk CTA + linked risk deep links; severity gate (high/critical); unit tests
- **Out of scope:** Near-miss lane (#964); Layout.tsx; RiskRegister.tsx changes; schema migrations (uses existing columns)
- **Feature flag / kill switch:** N/A — revert commit; `RAISE_RISK_ALLOWED_SEVERITIES` constant for policy tuning

## 2) Impact Map (what changed)
- **Frontend:** IncidentDetail Raise risk (high/critical only) + linked risks panel; `incidentsClient.raiseRisk`
- **Backend:** `incident_risk_links` helpers; incidents raise-risk route; GET incident exposes `linked_risk_ids` via route-level response extension
- **APIs:** `POST /api/v1/incidents/{id}/raise-risk`
- **Schemas:** Raise-risk request/response models defined in route module; `IncidentResponseWithLinks` for GET detail
- **Database:** None (uses existing `incidents.linked_risk_ids`, `risks_v2.linked_incidents`, `risks_v2.context`)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** `RAISE_RISK_ALLOWED_SEVERITIES` frozenset in `incident_risk_links.py`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + optional response field on GET detail
- **Tolerant reader / strict writer applied?** Yes — severity gate returns 400; owner FK validated before insert; `context` encoded as `incident:{id}|{ref}`
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit; existing linked rows remain harmlessly

## 4) Acceptance Criteria (AC)
- [x] AC-01: Raise risk creates `EnterpriseRisk` (`risks_v2`) with `context`/`linked_incidents` encoding incident
- [x] AC-02: Incident `linked_risk_ids` updated idempotently
- [x] AC-03: Only high/critical incidents can raise (400 otherwise)
- [x] AC-04: IncidentDetail exposes Raise risk action and linked risk deep links to `/risk-register?riskId=`
- [x] AC-05: Missing/invalid assignee does not 500 (FK-safe owner; IntegrityError → 409)
- [x] AC-06: Unit tests cover link helpers, severity gate, treatment map, owner resolve

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_incident_risk_links.py`
- [ ] Integration — deferred to CI / staging smoke

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** High/critical incident detail → Raise risk → enterprise risk created → navigate to `/risk-register?riskId=…`
- [x] **CUJ-02:** Incident shows linked risk id → deep link to risk register
- [x] **CUJ-03:** Medium/low incident → Raise risk hidden in UI; API returns 400 if forced

## 7) Observability & Ops
- **Logs:** Audit event `incident.risk_raised`; IntegrityError logged at exception
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open a high/critical staging incident → Raise risk → confirm 201 and Risk Register focus (no 500)
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Spot-check one raise-risk from high/critical incident

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
