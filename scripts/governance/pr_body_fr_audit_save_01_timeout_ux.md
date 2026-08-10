# Change Ledger (CL-FR-AUDIT-SAVE-01)

> Base: `origin/main` @ `c38f61478` (#1703 copilot runtime disclosure, LIVE).
> Frontend only — no alembic, no API surface change, no new flag.

## 1) Summary

- **Feature / Change name:** FR-AUDIT-SAVE-01 — Audit Template Builder saves
  survive multi-section templates, and a timeout tells the truth
- **User goal (1–2 lines):** An auditor saving a realistic 6-section /
  19-question template gets a save that completes, a visible sense of how far
  it has got, and — if it does time out — an honest "this much saved, reload
  before you try again" instead of being told to go fix a question that was
  never wrong.
- **Problem:** There is no bulk upsert endpoint, so one builder save is one
  HTTP request per section and per question — 26 sequential round trips for a
  6/19 template. That routinely exceeded the 45s default write timeout, and
  the resulting `ECONNABORTED` fell through the generic error path and was
  rendered as a per-question validation failure ("Review the highlighted
  details…", with a *Show question* jump). Authors re-entered changes that had
  already committed server-side.
- **In scope:**
  - Per-request 90s timeout for builder save writes only
  - Bounded concurrency (3) for question writes within a section
  - Save progress line in the template header (`aria-live="polite"`)
  - Timeout-shaped save error model: `isTimeout` / `maybeCommitted`, progress
    context, no misleading "fix this question" affordance
  - NEW `api/timeoutClassification.ts` (extraction from `client.ts`)
  - NEW `audit-builder/saveConcurrency.ts` (timeout config + limiter + copy)
- **Out of scope / deferred:**
  - Bulk section/question upsert endpoint (the actual fix for 26 round trips)
  - Auto-reconcile / re-fetch after a maybe-committed timeout — the user is
    told to reload; we do not silently re-read and merge
  - Any backend, schema, or API contract change
  - Partial-delete bookkeeping (see §3)
- **Feature flag / kill switch:** None — behavioural fix on an existing path;
  rollback is revert.

## 2) Impact Map (what changed)

- **Frontend:**
  - NEW `frontend/src/api/timeoutClassification.ts` — `WRITE_METHODS`,
    `TIMEOUT_STATUS_CODES`, `isTimeoutOrAbortError`,
    `classifyWriteTimeoutDisposition`, `isMaybeCommittedTimeout` moved verbatim
    out of `client.ts` so UI code can classify without importing the axios
    instance, store and toast wiring. `client.ts` re-exports all of them, so
    existing importers are untouched.
  - NEW `frontend/src/pages/audit-builder/saveConcurrency.ts` —
    `BUILDER_SAVE_TIMEOUT_MS = 90000`, `BUILDER_SAVE_REQUEST_CONFIG`,
    `BUILDER_SAVE_CONCURRENCY = 3`, `runWithConcurrency`,
    `formatQuestionProgress`.
  - `frontend/src/api/auditsClient.ts` — template/section/question write
    methods take an optional `AxiosRequestConfig`. Purely additive; every
    existing call site keeps the 45s default.
  - `frontend/src/pages/AuditTemplateBuilder.tsx` — save path passes the
    builder config on every write, runs a section's question writes three at a
    time, tracks stage + saved-question count, and feeds that progress into
    the error model.
  - `frontend/src/pages/audit-builder/saveErrorModel.ts` —
    `classifySaveTimeout` + `timeoutIssueModel`; `SaveIssueContext.progress`.
  - `frontend/src/pages/audit-builder/TemplateHeader.tsx` — optional
    `saveProgress` rendered next to the save button as `data-testid="save-progress"`.
- **Backend:** None.
- **APIs:** None. No route, payload, or status-code change.
- **Database:** None (no alembic).
- **Tests:** NEW `AuditTemplateBuilderSaveTimeout.test.tsx`, NEW
  `saveConcurrency.test.ts`; extended `saveErrorModel.test.ts`,
  `client.test.ts`, `auditsClient.test.ts`.
- **Docs:** This Change Ledger.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive throughout. The `config?` parameter is
  optional on every client method; `resolveRequestTimeout` already preserves a
  caller override that is not one of its own defaults, so the 90s value
  survives the request interceptor and no other caller's timeout moves.
- **Ordering safety under concurrency:** `buildQuestionPayload` always sends an
  explicit `sort_order`, so question ordering does not depend on arrival order.
  Sections stay strictly sequential because a section's persisted id is what
  the question payloads point at.
- **Duplicate-write safety:** Create POSTs already carry a per-request
  `Idempotency-Key` (`applyCreatePostIdempotency`), generated fresh per
  request, so running three creates in parallel cannot collide keys. The UI
  still refuses to auto-retry a maybe-committed write.
- **Failure containment:** `runWithConcurrency` stops scheduling as soon as a
  task throws, but awaits the lanes already in flight so a created question's
  returned id still reaches `questionIdMap` — a stopped save does not orphan
  ids and cause duplicate rows on the next attempt. It reports the
  lowest-index failure, so the message is deterministic.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy:** Revert the merge commit; no schema, no flag, no data.
- **Known adjacent gap (not introduced here, not fixed here):** if a save fails
  partway through the deleted-question / deleted-section sweep, the whole
  pending-delete list is retained, so a retry re-issues already-successful
  deletes and can 404. Pre-existing; called out rather than silently changed.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Save honesty on timeout | `ECONNABORTED` rendered as a per-question validation fault: "Review the highlighted details, fix the issue, then try saving again" | Rendered as `Save timed out (N of M questions saved)` with reconcile-then-retry guidance |
| Maybe-committed writes | Not surfaced; user invited to re-enter changes that may have committed → duplicate rows | `maybeCommitted` surfaced in copy: reload the template to see what saved before retrying |
| Misdirection affordance | *Show question* jump offered on a timeout, framing transport failure as an editing fault | No `questionId` on a timeout issue, so no *Show question* jump is rendered |
| Progress disclosure during long save | Spinner only; no indication of how far a 26-request save had got | `aria-live="polite"` progress line: stage, then `N of M questions saved` |
| Write timeout blast radius | Any raise would have to move the shared 45s `WRITE_TIMEOUT_MS` for every write in the app | Per-request 90s scoped to the builder save path only; asserted in `client.test.ts` |
| Timeout classification reuse | Lived in `client.ts`; UI import would drag in the axios instance + store + toasts | Isolated in `api/timeoutClassification.ts`; `client.ts` re-exports (no call-site churn) |
| Root cause vs symptom | — | Symptom is mitigated (timeout + concurrency + honest copy). Root cause — 26 round trips for one save — needs a bulk upsert endpoint and is explicitly deferred, not claimed as fixed |

## 4) Acceptance Criteria (AC)

- [x] AC-01: Builder save writes (template, section, question, delete) send
  `timeout: 90000`; every other caller keeps the 45s write default —
  `resolveRequestTimeout('patch', 90000) === 90000` and
  `90000 !== resolveRequestTimeout('post')`.
- [x] AC-02: Question writes within a section run at most 3 in flight;
  observed peak in-flight is exactly 3 in the component test, and
  `runWithConcurrency` never exceeds its limit in the unit test.
- [x] AC-03: A mid-save timeout produces "Save timed out", "may already have
  been saved", "reload this template"; it does **not** produce "Review the
  highlighted details" and does **not** render a *Show question* jump.
- [x] AC-04: The failure message states how far the save got — a failure on the
  last question of the second section reports `5 of 6 questions saved`.
- [x] AC-05: A timed-out save leaves no stuck state — the save button
  re-enables and the progress line clears; the save stops inside the failing
  section and never touches the next one.
- [x] AC-06: A non-timeout error (422 and friends) keeps its existing
  field-linked validation copy — a response status that is not 408/504 is
  explicitly *not* reclassified as a timeout.
- [x] AC-07: Change Ledger body present for `pnpm validate:pr-body` / gate
  checklist.
- [ ] AC-08: Bulk section/question upsert endpoint so one save is one request
  — **deferred** (follow-on; this PR mitigates, it does not remove the 26
  round trips).

## 5) Testing Evidence

Run locally in the worktree at `cc443f027`:

- [x] `npx vitest run src/api/auditsClient.test.ts src/api/client.test.ts
  src/pages/audit-builder/__tests__/saveErrorModel.test.ts
  src/pages/audit-builder/__tests__/saveConcurrency.test.ts
  src/pages/__tests__/AuditTemplateBuilderSaveTimeout.test.tsx`
  → **5 files, 46 tests passed**
- [x] Widened regression sweep
  `npx vitest run AuditTemplateBuilder audit-builder auditsClient`
  → **10 files, 75 tests passed**
- [x] `npx tsc --noEmit` → clean
- [x] `npx eslint <9 touched files> --max-warnings 0` → clean
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

Not verified: behaviour against a real slow backend. The timeout path is
exercised with a synthetic `ECONNABORTED` error shaped exactly as the axios
response interceptor stamps it (`isTimeout`, `maybeCommitted`,
`config.method`), not by a genuine 90s stall.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Auditor edits a 2-section / 6-question template and saves — all
  six question writes go out with the raised timeout, three at a time, the
  progress line shows, and no save-issue banner appears.
- [x] CUJ-02: A question write times out mid-save — the banner reports the
  timeout, says changes may already have been saved, names the progress, and
  the save stops without touching the following section.
- [x] CUJ-03: A save fails late (last question of the last section) — progress
  reads `5 of 6 questions saved` so the author knows what to reconcile.
- [ ] CUJ-04: Real slow-backend save on staging with a genuine 45–90s
  response — to verify on tip after deploy.

## 7) Observability & Ops

- **Playwright / test hooks:** `save-progress` (new), plus existing
  `save-issue-summary`, `save-issue-action-0`, `save-issue-show-0`,
  `save-issue-banner`.
- **Accessibility:** progress line is `aria-live="polite"` so a screen reader
  announces save progress without stealing focus.
- **Logs / Metrics:** none new. Timed-out builder writes remain visible via the
  existing axios error path.
- **Ops note:** if 90s proves insufficient, that is evidence for the bulk
  endpoint (AC-08), not for raising the number again.

## 8) Release Plan

1. Open PR on tip `c38f61478` (#1703 LIVE).
2. Merge only after ledger/compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark FR-AUDIT-SAVE-01 conveyor **PROD → DONE**. Merge alone is not
   done.
5. Follow-on: bulk upsert endpoint (AC-08).

## 9) Rollback Plan

- **Trigger:** Builder saves regress (ordering wrong, ids orphaned, duplicate
  questions after a retry), or the 90s timeout holds a request open long enough
  to degrade the app.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline
  deploy the reverted tip. Frontend-only, no schema and no flag, so the revert
  is complete on its own — no data repair and no `Emergency Rollback -
  Production` image restore needed.
- **Owner:** Platform Engineering (Audit Builder lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/audit-save-timeout-ux`
- Commit: `cc443f027`
- Base: `c38f61478` (#1703, PROD LIVE)
- Files: 12 changed (+823 / −84); 4 new
- Local evidence: 75 vitest tests green, `tsc --noEmit` clean, eslint clean
  (see §5)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — frontend only; no API/schema/alembic; client
  method signatures additive and backward compatible
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A (no flag, frontend behavioural fix)
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] No `Layout.tsx` / navigation shell edits (no overlap with the sidebar /
  Library shell lane)
- [x] No notification / deeplink edits (no overlap with #1702 `notif-csr-deeplink`)
- [x] No copilot / runtime-disclosure edits (no overlap with #1703)
- [x] No alembic revision, no backend source, no API contract
- [x] `client.ts` change is an extraction plus re-export — no behavioural change
  and no import churn for existing callers
- [x] Builds on #1700's save-error UX rather than replacing it: the validation
  path is untouched, timeouts branch before it
