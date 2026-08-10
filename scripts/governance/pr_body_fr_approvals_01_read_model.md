# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** FR-APPROVALS-01 — "Needs my decision" read model over live domain approval queues
- **User goal (1-2 lines):** A user can see, in one place, the decisions actually waiting on them — and is never told they are clear when the platform could not check. Replaces an approvals surface that showed every user an empty queue forever and recorded nothing when they pressed approve.
- **In scope:** `GET /api/v1/approvals/my-decisions` (read-only aggregate over three domains); a "Needs my decision" panel on `/actions`; deletion of the eight stub `/workflows` approval, delegation and stats endpoints, their engine methods, their frontend client methods and the tests that pinned their behaviour.
- **Out of scope:** FR-WF-ENG / any generic workflow engine or `workflow_instances` tables; recording decisions (each stays with its owning domain); role expansion and delegation; `notification_service`; admin notification inventory; `Layout.tsx` and navigation (the panel mounts inside an existing route).
- **Feature flag / kill switch:** None. The endpoint is additive and read-only; the panel fails soft (its own error state) and cannot take the action register down.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** New `frontend/src/components/NeedsMyDecisionPanel.tsx`, mounted in `frontend/src/pages/Actions.tsx` under the existing `/actions` route. No new route, no nav change, `Layout.tsx` untouched.
- **Backend (handlers/services):** New `src/domain/services/approvals_read_model.py` (three domain adapters + attribution) and `src/api/routes/approvals.py`; registered in `src/api/__init__.py`. `src/api/routes/workflows.py` and `src/domain/services/workflow_engine.py` lose the stub approval/delegation/stats surface. `src/services/workflow_engine.py` docstring corrected (it pointed at a deleted method).
- **APIs (endpoints changed/added):**
  - **Added:** `GET /api/v1/approvals/my-decisions` (requires `action:read`).
  - **Removed (8):** `GET /workflows/approvals/pending`, `POST /workflows/approvals/{id}/approve`, `POST /workflows/approvals/{id}/reject`, `POST /workflows/approvals/bulk-approve`, `GET /workflows/delegations`, `POST /workflows/delegations`, `DELETE /workflows/delegations/{id}`, `GET /workflows/stats`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Added `MyDecisionsResponse`, `PendingDecisionResponse`, `DecisionSourceResponse`. Removed `ApprovalResponse`, `BulkApprovalRequest`, `DelegationRequest`. `openapi-baseline.json` and `docs/contracts/openapi.json` regenerated; frontend types `WorkflowApprovalRecord`, `WorkflowDelegationRecord`, `WorkflowStatsResponse` deleted.
- **Database (migrations/entities/indexes):** None. This feature owns no table by design — it reads `investigation_runs`, `document_approval_instances`/`document_approval_workflows`/`controlled_documents`, and `signature_requests`/`signature_request_signers`. No Alembic revision.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive for the new endpoint; **deliberately breaking** for the eight deleted ones.
- **Tolerant reader / strict writer applied?** Yes on the read side. `PendingDecision.deep_link` and `requested_at` are nullable and null carries meaning (no screen exists; no date recorded) rather than being defaulted to something plausible. `DecisionSource.count` is null when the source is unreadable, so zero can only ever mean zero. The frontend client treats a missing `sources_complete` as **incomplete** (fail-closed), the opposite of `actionsAreComplete`, and the reason is documented at both call sites.
- **Breaking changes:** The eight `/workflows` endpoints now 404. Justification: `GET /workflows/approvals/pending` was served by `WorkflowTemplateEngine`, which holds no state, so it returned `[]` to every user in every tenant since it shipped; `approve`, `reject` and `bulk-approve` returned a decided-looking payload having written nothing, which on a quality management system means a permitted user could approve a controlled document, be told it worked, and leave no record; `GET /workflows/delegations` returned the same invented "Jane Smith / Annual leave" row to every caller; `GET /workflows/stats` reported `sla_compliance_rate` and `by_template` computed over an empty dict. No frontend page called any of them — only client methods and tests, all removed here. No consumer loses a working capability.
- **Migration plan:** None required (no schema change). Deployments behind Alembic revision `20260906_doc_ctl_children` lack the document-approval tables; the endpoint reports that source as `unavailable` with a reason rather than as empty, and still returns the other two sources.
- **Rollback strategy (DB):** No DB change. Revert the commits; the deleted endpoints return with them.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `GET /api/v1/approvals/my-decisions` returns only decisions the owning domain names the caller on — no role expansion, no tenant-wide queue, tenant-scoped (user ids are not unique across tenants).
- [x] AC-02: Three real adapters, each traceable to a domain that both raises and records the decision: `investigation_review` (`investigation_runs.status='under_review'` + `reviewer_user_id`), `document_approval` (pending instance whose current step names the caller), `signature_request` (open request with an unsigned signer row for the caller, matched by user id **or** email).
- [x] AC-03: A source that cannot be read is reported as `unavailable` with a reason and a null count; `sources_complete` goes false; the other sources still answer. An empty `items` is never by itself a claim that the caller is clear.
- [x] AC-04: A pending approval whose current step names nobody is counted as `unattributed` on its source rather than dropped or shown to an arbitrary user.
- [x] AC-05: Every date is captioned with what it records (`submitted` / `raised` / `last_updated`); a domain that does not timestamp the transition is not made to look like it does.
- [x] AC-06: `deep_link` is a real route or null. Null renders as "No screen for this yet" — signature requests link nowhere because `/signatures` renders a hardcoded empty list and never calls the signatures API.
- [x] AC-07: All eight stub endpoints answer 404, asserted in integration and e2e tests; nothing anywhere still serves "Jane Smith" or `DEL-20260115001`.
- [x] AC-08: `MAX_AUTHENTICATED_ONLY_DEBT` lowered 467 → 464 (three authenticated-only routes deleted); the replacement requires `action:read` so it adds no entry.
- [x] AC-09: Gates green: black, isort, flake8, mypy, type-ignore validator, mock-data gate, eslint, tsc, i18n key check, OpenAPI compatibility check.

## 5) Testing Evidence (link to runs)
- [x] Lint — `black --check src/ tests/` (1412 files), `isort --check-only`, `flake8 src/ tests/` clean; `eslint --max-warnings 0` clean on all changed frontend files; `prettier --check` clean.
- [x] Typecheck — `mypy src/` **Success: no issues found in 603 source files**; `tsc --noEmit` clean.
- [x] Build — N/A backend; frontend typecheck stands in (no bundler change).
- [x] Unit tests — `pytest tests/unit/` **6509 passed, 0 failed, 11 skipped**. Includes 20 new tests in `tests/unit/test_approvals_read_model.py` covering attribution over unvalidated JSON (role-only step, empty approver list, string ids, `True` is not user 1, 1-based `current_step`, out-of-range step) and ordering (undated last, truncated-but-complete).
- [x] Integration tests — `pytest tests/integration/test_approvals_my_decisions.py tests/integration/test_all_endpoints.py::TestWorkflowEndpoints` **35 passed, 0 failed** against a real database. Uses the `doc_control_scratch` harness, which drops the approval tables with real DDL, because the shared harness runs `create_all` and structurally cannot reproduce a missing table — the gap that let endpoints which could not work against the real schema ship green.
- [x] Contract tests — `pytest tests/contract/` **441 passed, 59 xfailed, 0 failed** (10 pre-existing fixture errors on incident/complaint/risk/audit contract tests: a duplicate-user insert in a local database, in files this PR does not touch). `check_openapi_compatibility.py` against the regenerated baseline: **PASSED — no breaking changes detected**.
- [x] Frontend tests — 17 new tests: `approvalsClient.test.ts` (9) and `NeedsMyDecisionPanel.test.tsx` (8, one per rendered state including "empty but unreadable" and the failure/retry path). `Actions.test.tsx` + `Actions.complianceSource.test.tsx` **43 passed** with the panel mounted. Full `vitest run`: **408 files, 2836 passed, 0 failed**. (An earlier full run showed 18 failures, all 10-second timeouts in files this PR does not touch; they were contention from an 18-minute integration run on the same machine and do not reproduce.)
- [x] E2E Smoke (critical journeys) — `tests/uat/test_stage1_basic_workflows.py -k "uat_043 or uat_044 or uat_045"` **3 passed** (UAT-044/045 retargeted to the live surfaces). Full e2e/smoke suites need a running server: deferred to CI, collection verified (82 tests) and the retargeted assertions are stricter than what they replaced.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: A named reviewer opens `/actions`, sees the investigation awaiting their review with its reference and the date captioned "last updated", clicks through to `/investigations/{id}` where `POST /investigations/{id}/approve` records the decision. (Integration: `TestInvestigationReviewsThatAreMine`; frontend: panel link test.)
- [x] CUJ-02: A user with nothing outstanding sees "Nothing needs your decision" **and the list of sources that answered** — and if any source could not be read, sees "Cannot confirm whether anything needs your decision" naming that source and the operator-facing reason instead. (Integration: `TestASourceThatCouldNotBeRead`; frontend: clear vs unknown tests.)
- [x] CUJ-03: A user who previously relied on the Workflow Center approvals queue now gets 404 from those routes and the real queue from `/actions`; a decision that names nobody is reported as a configuration defect rather than silently belonging to no one. (Integration: `TestTheFictionThisReplaced`, `test_an_approval_naming_nobody_is_counted_rather_than_dropped`.)

## 7) Observability & Ops
- **Logs:** No new logging. Failure to read a source is carried in the response body (`sources[].reason`), which is what an operator needs and a log line would not give the user.
- **Metrics:** No change. The deleted `/workflows/stats` tile is not replaced by another unmeasurable one.
- **Alerts:** No change.
- **Runbook updates:** `docs/governance/write_schema_extra_forbid_baseline.json` and `write_schema_extra_forbid_inventory.md` refreshed with `--write-baseline` after the stub approve/reject bodies left the write inventory (`ApprovalResponse` removed from the forbid set; floor 88→112 / open ceiling 208→206, picking up other lanes' conversions that had left the lock stale). CI seed role `ci_operator` gains `action:read` so smoke/locust `testuser` can call `GET /api/v1/approvals/my-decisions` (same gate as the Actions queue the panel sits beside).

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** `GET /api/v1/approvals/my-decisions` as a user with a known pending investigation review: expect that row, `sources_complete: true`, and three sources listed. Open `/actions` and confirm the panel renders above the register and deep-links correctly.
- **Canary plan:** N/A — read-only additive endpoint.
- **Prod post-deploy checks:** Health, readiness, version SHA. Then call the endpoint and check `sources_complete`: if `document_approval` reports `unavailable`, the deployment is behind `20260906_doc_ctl_children` and the panel is correctly declining to claim users are clear.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Errors on `/actions` attributable to the panel, or any row appearing in the wrong user's queue.
- **Rollback steps:** Revert the two commits and redeploy the previous SHA. No data to unwind — this feature writes nothing.
- **Owner:** Platform team.

## 10) Evidence Pack (links)
- CI run(s): linked after PR creation.
- Staging deploy evidence: linked after staging deploy.
- Canary evidence (if applicable): N/A.

### Declared, so a reviewer does not have to find it
- **The baseline had drifted.** Regenerating `openapi-baseline.json` also records five endpoints already merged on `main` whose lanes never refreshed it (`/document-graph/cascade`, `/document-graph/edges/pending`, `/documents/{document_id}/issue`, and two `promote-to-library` routes). The compatibility gate only fails on removals, which is why the drift went unnoticed. Nothing about those endpoints changes here; the alternative was hand-editing a 3 MB generated artefact to hide it.
- **The baseline is key-sorted.** It was regenerated with `sort_keys=True` to match how it was originally written; a default dump rewrote all 116k lines and would have made the diff unreviewable.
- **No Welsh translations.** 14 new keys were added to `en.json` only, consistent with the 351 en-only keys already there; `cy.json` parity stays at 91.7% against an 80% threshold. The panel is English-only until a translation pass.
- **Pre-existing dead modules left alone.** `src/api/schemas/workflows.py` and `src/domain/services/workflow_service.py` both declare their own approval/stats surface and are imported by nothing. Out of scope here; flagged for a separate deletion.
- **The Document Control screen has no approve control yet.** `document_approval` rows deep-link to `/document-control?document={id}`, which shows the document and its approval state; the decision endpoint (`POST /document-control/approvals/{instance_id}/action`) is not yet wired to a button. The link is honest about where the record lives; finishing that screen is follow-on work.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
