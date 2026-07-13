# Change Ledger (CL-PATH11-CUJ-NOTIFICATION-STANDARDS-PROPOSED)

## File allowlist (exclusive)
- `src/domain/services/standards_assessment_notifications.py` (NEW)
- `src/domain/services/governed_knowledge_service.py` (notify hook only)
- `tests/unit/test_standards_assessment_notifications.py` (NEW)
- `scripts/governance/pr_body_cuj_notification_standards_proposed.md`

**Zero overlap** with kill-operational-404s / health-alias / assessment-smoke / Layout.tsx.

## 1) Summary
- **Feature / Change name:** CUJ — Notify case owner when operational assess proposes standards links
- **User goal (1–2 lines):** Case owners/creators get an in-app notification with deep links to Exceptions (confirm/reject) and the case Standards tab when Assessor creates proposed links.
- **In scope:** Resolve owner/assignee + creator; create COMPLIANCE_ALERT in-app notifications; hook from `assess_operational_entity`; unit tests
- **Out of scope:** Email/SMS/push channels; Layout.tsx; health alias; assessment 404 resilience; near-miss raise-risk; investigation CAPA
- **Feature flag / kill switch:** N/A — revert commit (notification failures never block assess)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (consumes existing Notifications + Exceptions routes)
- **Backend (handlers/services):** `standards_assessment_notifications.py`; assess hook in `governed_knowledge_service.py`
- **APIs (endpoints changed/added):** None (side-effect of existing assess)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None (uses existing `notifications` table)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive side-effect
- **Tolerant reader / strict writer applied?** Yes — notify failures are swallowed; assess remains authoritative
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: When assess creates ≥1 proposed link, owner/assignee and/or creator receive in-app notification
- [x] AC-02: Notification `action_url` deep-links to Exceptions filtered by entity_type
- [x] AC-03: Notification metadata includes Standards tab deep link when a case route exists
- [x] AC-04: Assessor (sender) is not notified of their own run
- [x] AC-05: Zero links → no notification; notify failures never fail assess
- [x] AC-06: Unit tests cover deep links + notify skip/create paths

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_standards_assessment_notifications.py`
- [ ] Integration / E2E — deferred to CI + staging

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Operator assesses incident/near miss → proposed links → owner notified with Exceptions deep link
- [x] **CUJ-02:** Owner opens notification → Exceptions inbox filtered to entity type
- [x] **CUJ-03:** Assess with zero links or notify failure → case save/assess still succeeds

## 7) Observability & Ops
- **Logs:** warning on resolve/create failures; existing assess info logs
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Assess a case with assignee ≠ assessor; confirm notification row + deep link
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Spot-check one assess → notification

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Notification spam / incorrect recipients
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
