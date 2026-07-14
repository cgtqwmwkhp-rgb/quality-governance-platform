# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** GKB WL2 — Regulatory watch impacts create real Actions (owner/due/resolve)
- **User goal (1–2 lines):** Close the ops loop so regulatory watch impacts become assignable Actions with due dates and an explicit resolve/dismiss path — no more inbox rot.
- **In scope:** `regulatory_watch_actions` service; CAPASource.regulatory_watch; impact action/owner/due/resolve columns; knowledge-bank create-action + resolve endpoints; Compliance Automation Watch UI; Actions filter; unit tests; Change Ledger
- **Out of scope:** WL1 audit-pack provenance (#926 still open — `compliance.py` audit-pack + ComplianceEvidence download untouched); recurrence patterns; publish→rematch; Workforce; Assessor follow-ups
- **Feature flag / kill switch:** None — additive endpoints + columns; poll cycle only creates Actions at high confidence (≥0.85)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `ComplianceAutomation.tsx` Watch tab Create Action / Resolve / Dismiss; `knowledgeBankClient.ts` APIs; `Actions.tsx` regulatory_watch filter
- **Backend (handlers/services):** new `regulatory_watch_actions.py`; `regulatory_watch_service.py` auto-creates CAPA on high-confidence impacts; `governed_knowledge.py` create-action + resolve routes
- **APIs (endpoints changed/added):** `POST /api/v1/knowledge-bank/regulatory-watch/impacts/{id}/create-action`; `POST /api/v1/knowledge-bank/regulatory-watch/impacts/{id}/resolve`; enriched impacts list fields
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** RegulatoryImpactResponse + WatchActionResponse; CAPASource.regulatory_watch in unified Actions
- **Database (migrations/entities/indexes):** `20260713_regulatory_watch_actions` — capasource enum value + impact action/owner/due/resolve columns
- **Workflows/jobs/queues (if any):** existing Celery `run_regulatory_watch` now creates real CAPA Actions (no new beat schedule)
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive columns + endpoints; existing impacts remain `new` until Action created
- **Tolerant reader / strict writer applied?** Yes — UI tolerates missing action fields; create-action is idempotent
- **Breaking changes:** None
- **Migration plan:** Alembic `20260713_rw_actions` after `20260713_op_assess`
- **Rollback strategy (DB):** Drop new columns / FK; enum value `regulatory_watch` is irreversible on Postgres (safe leftover)

## 4) Acceptance Criteria (AC)
- [x] AC-01: High-confidence watch impacts auto-create CAPA Actions with owner + due date (status `task_created`)
- [x] AC-02: Manual `create-action` accepts optional owner/due/priority and links `action_id` on the impact
- [x] AC-03: `resolve` marks impact resolved and closes linked Action; `dismiss` closes without requiring Action
- [x] AC-04: Impacts list returns action_id / action_key / owner_id / due_date / resolve fields
- [x] AC-05: Unified Actions API recognises `regulatory_watch` source filter
- [x] AC-06: `#926` audit-pack surfaces (`compliance.py` / ComplianceEvidence download) untouched
- [x] AC-07: Unit tests cover create / idempotent / resolve / dismiss / enum mapping

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_regulatory_watch_actions.py` + existing `test_regulatory_watch_service.py`
- [ ] Full CI — linked after PR checks
- [ ] Staging smoke — deferred to Gate 3

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: HSEQ runs Watch → high-confidence impact auto-creates Action with owner/due → visible in Actions
- [x] CUJ-02: Operator opens Watch impact → Create Action → opens Action via action_key link
- [x] CUJ-03: Operator Resolve/Dismiss closes the inbox item (and linked Action when resolving)

## 7) Observability & Ops
- **Logs:** Action create/resolve via service logger + AiDecisionLog payloads
- **Metrics:** Existing CAPA metrics unchanged
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Run watch poll; confirm CAPA rows for high-confidence impacts; Create Action + Resolve from Watch UI; Actions filter `regulatory_watch`
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** `/api/v1/meta/version` SHA; smoke Watch create-action + resolve

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Spurious mass Action creation; create-action 5xx; resolve incorrectly closing unrelated CAPA
- **Rollback steps:** Revert app deploy; stop using create-action endpoints; leave additive columns in place
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main`
- Staging deploy evidence: pending
- Exclusive allowlist note: WL1 audit-pack (#926 OPEN) intentionally excluded

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
