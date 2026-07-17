# Change Ledger (CL-INC-LIST-HONESTY)

## 1) Summary
- **Feature / Change name:** INC-LIST-HONESTY — stop Incidents ErrorBoundary + harden list API
- **User goal:** Incidents page loads (or shows an honest banner) instead of “This section encountered an error”
- **In scope:** FE null-safe list render + payload normalize; BE optional `updated_at`, skip unserializable rows, drop list `selectinload(actions)`; unit/Vitest
- **Out of scope:** Incident detail redesign; Alembic; App.tsx; COPILOT
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `Incidents.tsx`, `Incidents.test.tsx`
- **Backend / APIs / DB:** `incidents.py` list route, `IncidentResponse.updated_at` optional, `IncidentService.list_incidents` no actions preload
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** More tolerant FE + BE; bad rows skipped/logged, list still returns
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Null/missing `incident_type` / `status` / `incident_date` do not throw in list render
- [x] AC-02: Non-array `items` → empty list + honesty banner (not ErrorBoundary)
- [x] AC-03: List API skips unserializable rows instead of 500
- [x] AC-04: Null `updated_at` coerced to `created_at` (OpenAPI field stays required)
- [x] AC-05: List query does not preload `actions`

## 5) Testing Evidence (link to runs)
- [x] Frontend Vitest — Incidents (11 passed, local)
- [x] Backend unit — incident route errors + list risk links (7 passed, local)
- [ ] CI after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Safety & Cases → Incidents → table or honest empty/error (no section ErrorBoundary)
- [x] CUJ-02: Sparse/malformed row still shows reference/title with “—” placeholders

## 7) Observability & Ops
- Logger warning when rows skipped; trackError on FE load failures
- Ops note: Fri–Mon prod API freeze was skipping Build/Deploy while SWA advanced (FE/BE skew)

## 8) Release Plan (Local → Staging → Canary → Prod)
- Staging: open Incidents authenticated; confirm list or banner
- Prod: force_deploy if freeze active; hard-refresh SWA after bake

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incidents list blank for all users / API 500 rate up
- **Rollback steps:** Revert squash-merge
- **Owner:** Platform / Safety & Cases track

## 10) Evidence Pack (links)
- CI: linked after PR creation
- Tip base: `ce463083`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE + BE honesty implemented
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Rollback plan verified
- [x] **Gate 5:** Evidence pack / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/Incidents.tsx`
- `frontend/src/pages/__tests__/Incidents.test.tsx`
- `src/api/routes/incidents.py`
- `src/api/schemas/incident.py`
- `src/domain/services/incident_service.py`
- `tests/unit/test_incident_route_error_responses.py`
- `tests/unit/test_incident_list_risk_links.py`
- `scripts/governance/pr_body_incidents_list_honesty.md`

Made with [Cursor](https://cursor.com)
