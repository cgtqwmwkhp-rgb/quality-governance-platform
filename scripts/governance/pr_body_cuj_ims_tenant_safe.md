# Change Ledger — Compliance CE-W1 IMS tenant-safe aggregations + metric honesty

## 1) Summary
- **Feature / Change name:** CE-W1 — IMS dashboard tenant-scoped aggregations and dual-metric honesty labels.
- **User goal (1-2 lines):** Executives and compliance officers see IMS metrics scoped to their tenant, with clear distinction between control-implementation % and evidence-coverage %.
- **In scope:** `ims_dashboard_service.py` tenant filters on standards/coverage/audit schedule; IMS banner honesty copy; unit + frontend tests.
- **Out of scope:** ComplianceEvidence page, Layout, Actions, Incident, Complaints, UVDB, Overview/Review static tabs (CE-W2+).
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend:** `IMSDashboard.tsx` — dual-metric banner labels (control implementation vs evidence coverage) when both API fields are live; single-metric fallback copy clarified.
- **Backend:** `ims_dashboard_service.py` — `tenant_id` on `get_standards_compliance`, `get_compliance_coverage`, `get_audit_schedule`; wired through `get_dashboard`.
- **APIs:** No contract change — `/api/v1/ims/dashboard` already passes `current_user.tenant_id`.
- **Database:** None.
- **Workflows:** None.
- **Documentation:** This change ledger only.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tenant filters aligned with `compliance.py` and `audits.py` semantics (tenant-owned rows + shared global catalog where applicable).
- **Breaking changes:** None for API schemas. Multi-tenant deployments may see lower counts (correct isolation vs prior cross-tenant leak).

## 4) Acceptance Criteria (AC)
- [x] AC-01: `get_compliance_coverage(tenant_id=…)` filters `ComplianceEvidenceLink` by tenant.
- [x] AC-02: `get_standards_compliance(tenant_id=…)` and `get_audit_schedule(tenant_id=…)` apply tenant filters consistent with compliance/audit routes.
- [x] AC-03: `get_dashboard` passes `tenant_id` to all tenant-scoped aggregations (standards, coverage, audit schedule, ISMS).
- [x] AC-04: IMS banner shows separate **Control implementation** and **Evidence coverage** labels when `compliance_coverage` is present.

## 5) Testing Evidence (link to runs)
- [x] `python3.11 -m pytest tests/unit/test_ims_dashboard_tenant_safe.py tests/unit/test_wave2_compliance_spine.py::test_ims_dashboard_coverage_counts_full_and_partial_links -q`
- [x] `npm test -- --run src/pages/__tests__/IMSDashboard.test.tsx`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Executive opens IMS hub — banner metrics are tenant-scoped and honestly labeled.
- [x] CUJ-02: Compliance officer cross-checks evidence coverage % on IMS vs Evidence Center (same tenant filter semantics).

## 7) Observability & Ops
- Existing `track_metric("ims_dashboard.loaded")` unchanged.
- No new secrets or env vars.

## 8) Release Plan (Local → Staging → Prod)
1. Squash-merge to `main` after CI green.
2. Staging auto-deploy via CI `workflow_run`.
3. Confirm staging tip + `/healthz` 200 (2×).
4. Force-deploy production with full 40-char `release_sha` when approved.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected empty IMS metrics for single-tenant installs or tenant filter regression.
- **Rollback steps:** Revert squash commit on `main`; redeploy previous known-good SHA.
- **Owner:** Platform maintainer.

## 10) Evidence Pack (links)
- AC-01..04 covered by unit + frontend tests in this PR.
- Closes residual gaps G3 (banner copy), G4, G5 from Compliance/IMS dual-lens audit.

---

## Change ledger (file-level)
- `src/domain/services/ims_dashboard_service.py` — tenant_id on standards/coverage/audit aggregations + helpers
- `src/api/routes/ims_dashboard.py` — unchanged (already passes tenant)
- `tests/unit/test_ims_dashboard_tenant_safe.py` — NEW tenant isolation tests
- `tests/unit/test_wave2_compliance_spine.py` — pass tenant_id in existing coverage test
- `frontend/src/pages/IMSDashboard.tsx` — dual-metric honesty labels
- `frontend/src/pages/__tests__/IMSDashboard.test.tsx` — honesty label assertions

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + Change Ledger complete
- [x] **Gate 1:** No API/schema/DB contract change — tenant filter behaviour only
- [ ] **Gate 2:** CI required checks green
- [ ] **Gate 3:** Staging tip == merge SHA
- [ ] **Gate 4:** Prod tip == prod SHA (post-deploy)
- [ ] **Gate 5:** Evidence recorded in this PR

## Test plan
- [ ] Backend unit tests pass
- [ ] Frontend IMSDashboard tests pass
- [ ] Manual: two tenants with distinct evidence links see different IMS coverage counts
