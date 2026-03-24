# Critical User Journey (CUJ) — Test Traceability Matrix

**Product:** Quality Governance Platform v2.x  
**Last updated:** 2026-03-20  
**Purpose:** Map the ten agreed critical user journeys to automated/regression tests under `tests/e2e/`, `tests/uat/`, `tests/smoke/`, and `tests/unit/`.

**How to read “Test count”**

- **UAT:** Fixed-size suites — `tests/uat/test_stage1_basic_workflows.py` (50 tests) and `tests/uat/test_stage2_sophisticated_workflows.py` (20 tests). Per-CUJ counts below list **only tests that materially exercise that journey** (not the whole file).  
- **E2E:** Full collection size is tracked in `docs/evidence/e2e_baseline.json` (currently **43** passing tests as the baseline gate). Individual files contribute overlapping coverage.  
- **Smoke:** `tests/smoke/test_enterprise_smoke.py` — enterprise smoke suite (multiple classes; see file). Quarantined smoke: `tests/smoke/test_phase3_phase4_smoke.py` (skipped — see `tests/smoke/QUARANTINE_POLICY.md`).  
- **Unit:** `tests/unit/` — Python unit tests (domain, security, models, etc.); counts vary by module. Frontend component/unit tests run via Vitest in `frontend/` (not under `tests/unit/`); they are **not** counted in the Unit column unless copied here for traceability notes.

**Coverage status**

- **Covered** — Dedicated or strong automated coverage of the journey’s main path.  
- **Partial** — Surrounding APIs, auth, or portal flows covered; sub-steps (e.g. witness tab, file upload, running sheet) thin or environment-dependent.  
- **Gap** — No reliable automated test found for the primary user-visible action; manual/UAT script or new test required.

---

## Traceability matrix

| CUJ ID | CUJ name | Test file(s) | Test count (journey-related) | Coverage status |
|--------|----------|--------------|------------------------------|-----------------|
| **CUJ-01** | Employee reports an incident | `tests/uat/test_stage1_basic_workflows.py` (`TestEmployeePortalWorkflows::test_uat_001_submit_incident_report`, `test_uat_004_track_report_by_reference`, …); `tests/uat/test_stage2_sophisticated_workflows.py` (`test_suat_001_full_incident_lifecycle_via_portal`); `tests/e2e/test_portal_e2e.py` (`TestIncidentReporting`, `TestReportTracking`); `tests/e2e/test_full_workflow.py` (`TestIncidentLifecycle`, `TestEmployeePortalFlow`); `tests/e2e/test_enterprise_e2e.py` (`TestIncidentLifecycleE2E`, `TestNewEmployeeJourneyE2E`); `tests/smoke/test_enterprise_smoke.py` (portal smoke classes as applicable) | UAT: ~12 journey-focused; E2E: ~15+ across files; Smoke: subset | **Covered** |
| **CUJ-02** | Manager creates CAPA action from incident | `tests/e2e/test_enterprise_e2e.py` (`TestAuditLifecycleE2E` — lifecycle narrative includes CAPA; primarily audit/findings endpoints); `tests/e2e/test_full_workflow.py` (`TestAuditWorkflow`); `tests/uat/test_stage1_basic_workflows.py` (`TestIncidentManagementWorkflows` — auth/list/update guards, not full CAPA create) | E2E: ~2–4 weakly aligned; UAT: indirect | **Gap** (no dedicated “create CAPA from incident” E2E; add API/UI test) |
| **CUJ-03** | Driver completes daily vehicle checklist | _No dedicated file found under `tests/e2e/` or `tests/uat/` in current tree_; `tests/smoke/test_enterprise_smoke.py` may touch fleet health indirectly | 0 journey-specific | **Gap** |
| **CUJ-04** | User reports an RTA with third party details | `tests/e2e/test_portal_e2e.py` (`TestRTAReporting::test_submit_rta_report`); `tests/e2e/test_full_workflow.py` (`TestEmployeePortalFlow::test_rta_report_flow`); `tests/uat/test_stage1_basic_workflows.py` (`TestRTAManagementWorkflows` — authenticated RTA API auth guards) | E2E: 2; UAT: ~5 (auth/contract, not full portal RTA happy path) | **Partial** (portal RTA may return 404 per TODOs in tests; needs stabilised contract) |
| **CUJ-05** | Witness details added to RTA | `tests/uat/test_stage1_basic_workflows.py` (`TestRTAManagementWorkflows` — generic RTA endpoints) | UAT: indirect (~2) | **Gap** (no explicit witness sub-resource test located) |
| **CUJ-06** | User uploads evidence photos | `tests/e2e/test_enterprise_e2e.py` / `test_full_workflow.py` (evidence endpoints where `GET /api/v1/compliance/evidence` appears — read-only); `tests/unit/` may include upload utilities if present | 0–2 (read-only) | **Gap** (multipart/evidence upload journey not traced to a single test) |
| **CUJ-07** | Running sheet entry added to RTA | `tests/uat/test_stage1_basic_workflows.py` (`TestRTAManagementWorkflows::test_uat_035_rta_actions_require_auth` — actions endpoint auth only) | 1 | **Gap** |
| **CUJ-08** | Admin creates and assigns an audit | `tests/e2e/test_admin_e2e.py` (`TestAuditManagement`); `tests/e2e/test_full_workflow.py` (`TestAuditWorkflow`); `tests/e2e/test_enterprise_e2e.py` (`TestAuditLifecycleE2E`); `tests/smoke/test_enterprise_smoke.py` (if audit endpoints in critical list) | E2E: ~6–10 across files | **Partial** (template create sometimes accepts 404; list/findings covered) |
| **CUJ-09** | User submits a complaint | `tests/uat/test_stage1_basic_workflows.py` (`test_uat_002_submit_complaint_report`); `tests/uat/test_stage2_sophisticated_workflows.py` (`test_suat_002_complaint_with_status_tracking`); `tests/e2e/test_portal_e2e.py` (`TestComplaintReporting`); CI stability guard references complaint tests | UAT: ~3; E2E: ~1–2 | **Covered** |
| **CUJ-10** | Investigation created and actions tracked | `tests/e2e/test_enterprise_e2e.py` (`TestIncidentLifecycleE2E::test_incident_with_investigation`); `tests/uat/test_stage1_basic_workflows.py` (`test_uat_017_get_incident_investigations_requires_auth`, complaint investigation auth); `tests/e2e/test_full_workflow.py` (`TestIncidentLifecycle::test_full_incident_workflow` — partial narrative) | E2E: ~1–2; UAT: ~3 | **Partial** (investigations listed; action tracking not fully asserted end-to-end) |

---

## Quick reference — suite locations

| Suite | Path | CI / evidence |
|-------|------|----------------|
| E2E | `tests/e2e/` | `pytest tests/e2e/`; baseline `docs/evidence/e2e_baseline.json` |
| UAT | `tests/uat/` | `test_stage1_basic_workflows.py`, `test_stage2_sophisticated_workflows.py` |
| Smoke | `tests/smoke/` | `pytest tests/smoke/` (blocking in CI) |
| Unit | `tests/unit/` | `pytest tests/unit/` |

## Follow-up actions

1. Add **CUJ-02**, **CUJ-03**, **CUJ-05–CUJ-07**, **CUJ-06** targeted tests (E2E or UAT) with stable API contracts, including the expanded runner-sheet flows for incidents, complaints, and near misses.  
2. Remove or update **404-tolerant** assertions on RTA portal routes once `/api/v1/portal/rta` is final.  
3. Re-baseline E2E counts in `docs/evidence/e2e_baseline.json` after new CUJ tests land.
