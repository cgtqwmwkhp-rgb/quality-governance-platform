# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Golden-Thread residual R67 — GKB controlled-document evidence read path
- **User goal (1–2 lines):** Let document-control staff inspect the real GKB evidence recorded for one unambiguous, same-tenant library-document candidate while clearly distinguishing that candidate from a governed controlled→library relationship.
- **In scope:** Controlled-document golden-thread read endpoint; GKB evidence-link serialization; Document Control UI inspection panel; focused unit tests; Change Ledger.
- **Out of scope:** A controlled-document → library-document FK, data backfill/reconciliation UI, automatic publish-event emission, and publish-lifecycle side effects.
- **Feature flag / kill switch:** None — additive read-only endpoint and on-demand UI panel.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `DocumentControl.tsx` adds an on-demand “GKB evidence chain” panel; `documentControlClient.ts` adds its typed API contract.
- **Backend (handlers/services):** `document_control.py` adds a tenant-scoped read endpoint and wires `decide_golden_thread_publish` into its integrity response.
- **APIs (endpoints changed/added):** `GET /api/v1/document-control/{document_id}/golden-thread`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Typed frontend DTO exposes candidate, evidence links, integrity state, and deny-safe publish plan.
- **Database (migrations/entities/indexes):** None. Current schema has no controlled-document → library-document FK.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive, authenticated tenant-scoped read path; existing control and GKB APIs remain unchanged.
- **Tolerant reader / strict writer applied?** Yes — a title/reference-number match is labelled `unverified_candidate`; ambiguous matches expose no candidate or evidence.
- **Breaking changes:** None.
- **Migration plan:** None in this MVP.
- **Rollback strategy (DB):** Revert application deploy; no persisted data changes.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Staff can request a controlled document’s evidence-chain read model from Document Control.
- [x] AC-02: Only one unambiguous, same-tenant library-document candidate is displayed.
- [x] AC-03: Candidate GKB evidence links expose actual recorded status, clause, scheme, signal type, confidence, and rationale.
- [x] AC-04: UI states explicitly that candidate evidence is not controlled-document evidence without a hard FK.
- [x] AC-05: Planner output records the hard-FK gap and never causes a publish side effect.
- [x] AC-06: Focused tests prove candidate evidence and ambiguity handling.

## 5) Testing Evidence (link to runs)
- [x] Backend unit — `pytest -q tests/unit/test_gkb_golden_thread.py tests/unit/test_gkb_golden_thread_read_path.py tests/unit/test_document_version_control_cuj.py` — 13 passed.
- [x] Static diagnostics — IDE diagnostics report no errors in changed backend, frontend, and test files.
- [x] Frontend lint/build — `npm run lint && npm run build` passed.
- [ ] Full CI — link after PR creation.
- [ ] Staging smoke — deferred to Gate 3.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staff inspect an exact single candidate and see its real GKB evidence link(s) plus unverified relationship warning.
- [x] CUJ-02: Multiple candidate library documents return `ambiguous` and deliberately disclose no evidence chain.
- [x] CUJ-03: Read path exposes `hard_fk_absent`; it does not publish or invoke GKB lifecycle hooks.

## 7) Observability & Ops
- **Logs:** None new; endpoint is read-only.
- **Metrics:** None new.
- **Alerts:** None new.
- **Runbook updates:** Staff should resolve duplicate candidate records or wait for the FK migration; the UI does not establish a relationship.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open Document Control, select a document with exactly one same-tenant title/reference candidate, inspect evidence; repeat with duplicate candidates and verify no evidence is shown.
- **Canary plan:** Promote after staging and CI are green.
- **Prod post-deploy checks:** Authenticated `GET /api/v1/document-control/{id}/golden-thread`; confirm response says `unverified_candidate` or `ambiguous`, never a verified relationship.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Cross-tenant exposure, ambiguous evidence displayed, or staff are told candidate evidence is governed controlled-document evidence.
- **Rollback steps:** Revert this PR deployment; no data repair required.
- **Owner:** David Harris / Platform ops.

## 10) Evidence Pack (links)
- CI run(s): pending PR checks.
- Base branch: `origin/main`.
- Staging deploy evidence: pending.

## Deferred
- **DEFER — hard FK and publish lifecycle:** Add a nullable `controlled_documents.library_document_id` FK with tenant-safe migration/backfill and explicit steward reconciliation; then invoke `gkb_publish_lifecycle` only after a successful controlled publish. The present schema cannot prove this relationship, so this MVP deliberately provides a read-only, labelled candidate path and does not emit events.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** API/Data/UX contracts approved (additive, read-only, honest candidate labelling).
- [ ] **Gate 2:** CI green (frontend lint/build and full checks pending PR).
- [ ] **Gate 3:** Staging verification complete (evidence linked).
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked).
- [x] **Gate 5:** Production verification plan + monitoring ready.
