# Complaints create Wave 1 — intake fields + evidence attach

## Summary
- Extend complaint intake with customer (`contract_id`), channel (`source_type` + `in_person`), subject (`subject_user_id` / `subject_name`), alleged event time, and complainant company on create/update.
- Redesign New Complaint modal groups: Customer → Parties → Channel & topic → When → Narrative → Attachments.
- Post-create multi-file upload via shared `evidence-assets` spine (`source_module=complaint`).

## Test plan
- [ ] Migration `20260721_cmp_intake` applies cleanly
- [ ] `pytest tests/unit/test_complaint_validation.py` — intake + update fields
- [ ] FE `Complaints.test.tsx` — create requires customer; navigates to detail
- [ ] Manual: create with contract + channel + attachment; open detail
