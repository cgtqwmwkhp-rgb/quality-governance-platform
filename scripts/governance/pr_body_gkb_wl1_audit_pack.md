# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** GKB WL1 — server-side audit pack with full provenance
- **User goal (1–2 lines):** Replace client-assembled ISO audit pack download with a server export that is attributable, timestamped, and signal-honest for certification auditors.
- **In scope:** `GET /api/v1/compliance/audit-pack`; provenance serialization; ComplianceEvidence download wiring; unit/integration honesty tests; Change Ledger
- **Out of scope:** Workforce; Assessor follow-up branches; ZIP packaging; dedicated `confirmed_by` DB column; recurrence / regulatory inbox / golden-thread uplifts
- **Feature flag / kill switch:** None — additive endpoint; UI switches to server export only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `ComplianceEvidence.tsx` downloads via `complianceApi.downloadAuditPack`
- **Backend (handlers/services):** `compliance.py` audit-pack route; `iso_compliance_service.build_audit_pack` + provenance serializers
- **APIs (endpoints changed/added):** `GET /api/v1/compliance/audit-pack` (JSON attachment)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Audit pack JSON contract with provenance_policy + evidence_links
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint; existing `/report` and `/soa` unchanged
- **Tolerant reader / strict writer applied?** Yes — legacy null `signal_type` remains conformance-eligible; NC/gap/opportunity excluded by default and labelled when included
- **Breaking changes:** None (UI download source changes to server pack; shape is richer)
- **Migration plan:** None
- **Rollback strategy (DB):** Revert app deploy; no schema change

## 4) Acceptance Criteria (AC)
- [x] AC-01: Server audit pack exports created_at, created_by/actor, rationale, confidence, signal_type, scheme/standard, clause_id, entity_type/id, status, confirmed_at/by when available
- [x] AC-02: Default export excludes nonconformity/gap/opportunity from conformance `evidence_links` and lists them under `operational_signals`
- [x] AC-03: `include_nonconformity=true` retains NC rows with honest `signal_label` / `conformance_eligible=false`
- [x] AC-04: ComplianceEvidence download calls server audit-pack endpoint
- [x] AC-05: Unit + route tests prove NC exclude/label behaviour

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_audit_pack_provenance.py`
- [x] Integration/route — `tests/integration/test_audit_pack_export.py`
- [ ] Full CI — linked after PR checks
- [ ] Staging smoke — deferred to Gate 3

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor opens Compliance Evidence → Download Audit Pack → receives server JSON with provenance_policy
- [x] CUJ-02: NC-linked CEL does not appear in default conformance evidence_links
- [x] CUJ-03: include_nonconformity=true returns NC labelled as operational_nonconformity / not conformance-eligible

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None (response headers `X-Audit-Pack-Version`, `X-Audit-Pack-Nonconformity-Mode`)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Download pack for tenant with mixed evidence + NC links; confirm NC excluded by default and present under operational_signals
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** `/api/v1/meta/version` SHA; smoke `GET /api/v1/compliance/audit-pack`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Audit pack 5xx; pack missing required provenance fields; NC incorrectly treated as conformance evidence
- **Rollback steps:** Revert this PR deploy; UI can temporarily fall back to prior client assemble if needed
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main` (post-#924 coverage honesty)
- Staging deploy evidence: pending

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
