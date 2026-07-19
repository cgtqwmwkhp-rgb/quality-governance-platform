# Change Ledger (CL-UAT-A1-INCIDENT-409)

## File allowlist (exclusive)
- `src/domain/services/incident_service.py`
- `src/domain/services/incident_risk_links.py`
- `src/api/routes/incidents.py`
- `tests/unit/test_incident_service.py`
- `tests/unit/test_incident_risk_links.py`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/__tests__/IncidentDetail.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_uat_a1_incident_409.md`

## 1) Summary
- **Feature / Change name:** UAT A1 — PX-002 incident edit 409 swallowed + PX-032 raise-risk 409
- **User goal (1–2 lines):** Operators can save incident edits and raise enterprise risks without silent failures or opaque 409 conflicts.
- **Depends on:** Existing incident PATCH + raise-risk enterprise path (#966).
- **In scope:** Same-status transition no-op; FE toast on save failure; status dropdown aligned to `IncidentStatus`; raise-risk tenant fallback + idempotent recovery; unit/vitest proofs; this Change Ledger.
- **Out of scope:** Near-miss raise-risk rewrite; Layout.tsx; schema migrations; CAPA/investigation 409 paths.
- **Feature flag / kill switch:** N/A (bugfix) — revert commit.

## 2) Impact Map
- **Frontend:** `IncidentDetail` save toast + omit unchanged status; status select uses `reported` / full lifecycle values.
- **Backend:** `validate_incident_transition` allows same-status; raise-risk resolves tenant, returns existing linked risk, recovers after IntegrityError race.
- **APIs:** `PATCH /api/v1/incidents/{id}` no longer 409s on no-op status; `POST .../raise-risk` idempotent when risk already linked.
- **Schemas/contracts:** Unchanged response shapes.
- **Database:** None.
- **Observability:** Clearer raise-risk 409 message; existing audit event retained on create path.

## 3) Compatibility & Data Safety
- Additive behaviour only; invalid status jumps still return 409 `INVALID_STATE_TRANSITION`.
- Raise-risk still creates `EnterpriseRisk` (`risks_v2`) with junction dual-write.
- Status label `open` removed from incident edit UI (was never a valid `IncidentStatus`).

## 4) Acceptance Criteria
- [x] AC-01: Same-status PATCH (`reported`→`reported`) does not raise `StateTransitionError`.
- [x] AC-02: Incident edit save failure shows a toast with API message (PX-002).
- [x] AC-03: Status dropdown includes `reported` and omits invalid `open`.
- [x] AC-04: Raise-risk uses tenant fallback; idempotent when risk already linked; IntegrityError recovers existing risk when present (PX-032).
- [x] AC-05: Unit + vitest coverage for transition noop, tenant guard, save toast / status omit.

## 5) Testing Evidence
- [x] Unit: `pytest tests/unit/test_incident_service.py tests/unit/test_incident_risk_links.py -q`
- [x] Frontend: `npx vitest run src/pages/__tests__/IncidentDetail.test.tsx`
- [ ] CI: PR checks
- [ ] Staging/prod spot-check: edit reported incident Save → 200; Raise risk on high/critical → 201 (or linked existing)

## 6) Critical Journeys
- [x] CUJ-01: Incident detail → Edit → Save Changes (title/description) succeeds without 409.
- [x] CUJ-02: Save Errors surface toast (no silent swallow).
- [x] CUJ-03: High/critical incident → Raise risk creates or returns linked enterprise risk (no dead 409).

## 7) Rollback Plan
- **Owner:** Platform release operator
- **Rollback steps:** Revert merge commit / redeploy prior tip SHA. No DB migration.

## 8) Observability & Operations
- **Logs:** Existing `raise-risk IntegrityError` exception log; audit `incident.risk_raised` on create.
- **Alerts:** Existing API 4xx/5xx.
- **Runbook:** If raise-risk still 409s, inspect IntegrityError constraint name in API logs; confirm `risks_v2.tenant_id` and reference uniqueness.

## 9) Release Plan
- **Staging:** Merge → tip deploy → spot-check CUJ-01/03.
- **Production:** Promote with tip==LIVE after staging green.

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- Staging deploy evidence: pending

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Reuses existing incident/risk APIs; no second stack
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging/prod evidence linked
- [x] **Gate 4:** N/A canary (behaviour fix)
- [x] **Gate 5:** Rollback + observability documented
