# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Complaint raise-risk parity (SYS-04)
- **User goal (1-2 lines):** Staff can raise an Enterprise Risk Register entry from a Complaint detail page, matching Near Miss / Incident stitch.
- **In scope:** API `POST /complaints/{id}/raise-risk`, enterprise helper, `linked_risk_ids` on complaint response, FE button + client, i18n EN/CY, OpenAPI baseline sync, regression unit tests.
- **Out of scope:** Evidence `:read` permission matrix, portal complaint type lookups, soft-delete cases, lessons API close gate.
- **Feature flag / kill switch:** N/A — gated by existing `risk:create` permission.

## 2) Impact Map (what changed)
- **Frontend:** `ComplaintDetail.tsx` Raise risk action; `complaintsClient.ts` types + `raiseRisk`; i18n en/cy keys.
- **Backend:** `complaint_risk_links.py` helper; `complaints.py` raise-risk route; `ComplaintResponse.linked_risk_ids`.
- **APIs:** New `POST /api/v1/complaints/{complaint_id}/raise-risk` (201).
- **Schemas/contracts:** OpenAPI baseline + docs contracts regenerated.
- **Database:** None (uses existing `linked_risk_ids` + `case_risk_links`).
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + response field; existing clients ignore `linked_risk_ids` until upgraded.
- **Migrations / backfill:** None.
- **PII / tenancy:** Tenant-scoped via ComplaintService.get_complaint; risk inherits complaint.tenant_id.

## 4) Acceptance Criteria
- [x] AC-01: Raise risk creates EnterpriseRisk (risks_v2), not legacy Risk
- [x] AC-02: Complaint.linked_risk_ids updated + case_risk_links synced
- [x] AC-03: FE button navigates to risk register with new risk
- [x] AC-04: Requires `risk:create`
- [x] AC-05: OpenAPI contract regenerated

## 5) Test plan
- [x] Unit: `tests/unit/test_complaint_raise_risk_enterprise_path.py`
- [ ] Manual: open Complaint detail → Raise risk → confirm register entry + linked ids
