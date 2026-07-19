# Change Ledger (CL-GOV-LIB-W3-REVIEW-PACKS)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W3 — review packs + horizon stubs
- **User goal (1–2 lines):** Open a 90-day review pack for a filed document, capture stub AI horizon findings that require human confirm/reject, close only when none remain pending, and expose 3/6/12-month review horizons plus daily reminder banding.
- **Depends on:** #1179 LIVE (W2 on tip `b942a86`); Alembic head `20260719_merge_gov_lib_cg`
- **In scope:** Alembic `library_review_packs` + `regulatory_findings`; open/confirm/reject/close/scan APIs; horizons JSON; stub horizon adapter; Celery reminder classifier + daily horizon sweep; unit tests; Change Ledger
- **Out of scope:** FE review UI; Excel export polish; live Perplexity/Claude/OpenAI network calls; rich internal joins for incidents/audits; disposal (W5); HSEQ approve→campaign (W4)
- **Feature flag / kill switch:** `LIBRARY_HORIZON_PROVIDER=stub` (default) — no network; live providers are no-op wrappers until a follow-up

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `library_review_service.py`, `library_horizon_adapter.py`, models `library_review.py`
- **APIs (endpoints changed/added):** `/api/v1/library-review/*` (horizons, packs CRUD-ish, confirm/reject/close, horizon-scan)
- **Schemas/contracts:** Additive OpenAPI only (`src/api/schemas/library_review.py`)
- **Database (migrations/entities/indexes):** `20260719_gov_lib_w3_review` — tables + partial unique open pack index
- **Workflows/jobs/queues:** Celery `check_library_review_reminders` (daily 07:45) + `run_library_horizon_scan` (daily 08:00 sweep / on-demand)
- **Config/env/flags:** `LIBRARY_HORIZON_PROVIDER`, optional `PERPLEXITY_API_KEY`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive schema + routes only
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** Alembic upgrade from `20260719_merge_gov_lib_cg`
- **Rollback strategy (DB):** Alembic downgrade drops both tables; revert PR on main
- One open pack per document enforced by partial unique index + app check
- Close gated on zero `pending` findings (`StateTransitionError` / 409)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Migration from `20260719_merge_gov_lib_cg` creates `library_review_packs` + `regulatory_findings`
- [x] AC-02: Pack opens only when `review_date` within 90 days or overdue; one open pack per document
- [x] AC-03: Horizon scan (stub) persists `regulatory_findings` with `disposition=pending` + `provider`
- [x] AC-04: Confirm/reject sets disposition + actor/timestamp; close succeeds only when zero pending
- [x] AC-05: Close with pending findings raises `StateTransitionError`
- [x] AC-06: `GET /horizons?months=3|6|12` returns bucketed counts + thin rows from `documents.review_date`
- [x] AC-07: Daily reminder + horizon tasks registered on Celery beat; band classifier unit-tested
- [x] AC-08: `internal_inputs` present on pack (stub lists)
- [x] AC-09: Unit tests in `tests/unit/test_gov_lib_w3_review_packs.py` (≥8) — no live AI
- [x] AC-10: Change Ledger complete with CUJ-01+

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_gov_lib_w3_review_packs.py` (local)
- [ ] CI — this PR
- [ ] Staging verification — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens pack for doc due in 45d → stub scan → confirm/reject all → close OK
- [x] CUJ-02: Close with one pending finding → `StateTransitionError`
- [x] CUJ-03: Horizons `months=12` returns overdue + due + upcoming buckets for seeded `review_date`s
- [x] CUJ-04: Reminder band classifier maps 90/60/30/7/overdue exclusively

## 7) Observability & Ops
- **Logs:** Reminder sweep + horizon sweep emit structured count summaries; live providers log skip (no network)
- **Metrics:** No new metrics in this thin wave
- **Alerts:** No new alerts
- **Runbook updates:** Set `LIBRARY_HORIZON_PROVIDER=stub` in all envs until live adapter follow-up; Celery beat must include the two new daily entries

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Alembic upgrade; `GET /library-review/horizons?months=3`; open pack for in-window doc; stub scan; confirm; close
- **Canary plan:** N/A — additive/opt-in; stub provider default
- **Prod post-deploy checks:** tip_match YES; beat entries present; no unexpected outbound AI calls (provider=stub)

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Pack open/close incorrectly blocking reviews, or horizon sweep writing unexpected volume
- **Rollback steps:** Revert PR on main; Alembic downgrade `20260719_gov_lib_w3_review`; force_deploy prior SHA
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After tip deploy
- Canary evidence (if applicable): N/A
- Unit evidence: `pytest tests/unit/test_gov_lib_w3_review_packs.py`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (additive-only; no FE)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A, additive/opt-in stub rollout
- [x] **Gate 5:** Production verification plan + monitoring ready
