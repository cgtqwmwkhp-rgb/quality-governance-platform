# Change Ledger (CL-FR-NOTIF-ADMIN-01-FIX-01)

> Base: `origin/main` @ `d3c92175f` (#1711 FR-NOTIF-ADMIN-01).
> A wrong sentence in the inventory, and a test so it cannot go wrong again
> silently. **No alembic revision, no schema change, no API change, no UI change.**

## 1) Summary

- **Feature / Change name:** FR-NOTIF-ADMIN-01 fix — correct the CAPA closure
  producer's category-gating claim
- **User goal:** The inventory exists so an administrator can trust what it says
  about who gets told what. A note that overstates gating is the defect this
  feature was built to remove, so it is worth its own PR rather than a quiet edit
  in a later one.
- **Problem:** #1711 declared, for the `audit_finding_capa_closure` producer, that
  "an explicitly requested channel is still narrowed by category preferences, so
  asking for in-app is not the same as guaranteeing the websocket push". That is
  true of only one of the producer's two outcomes. `notify_capa_closure_bridge`
  (`src/domain/services/audit_service.py`) picks its type from the destination
  status:
  - **pending verification** → `NotificationType.AUDIT_FINDING`, which
    ADMIN-03 maps to `audit_notifications`, so that toggle *can* hold the push
    back;
  - **closed** → `NotificationType.ACTION_COMPLETED`, which **no** category owns.
    `create_status` defaults to `MEDIUM` priority, so `categories_for()` returns
    nothing at all (`high_priority_alerts` is added only for `HIGH`), and
    `is_channel_muted` therefore never suppresses. Quiet hours do not apply to
    in-app either.

  So for the closure notification — the more consequential of the two — no
  preference can suppress it, and the previous note said one could. Found by
  Bugbot on #1711 and verified against the merged source before changing anything.
- **In scope:** the note text, and one test pinning the two mapping facts it
  depends on.
- **Out of scope:** the mapping itself. Whether `ACTION_COMPLETED` *should* belong
  to a category is an ADMIN-03 behaviour question; changing it would alter
  delivery for every status notification in the product, which is not a
  documentation fix. Recorded here as a question for that lane, not answered.
- **Feature flag / kill switch:** none; this changes reported text, not behaviour.

## 2) Impact Map (what changed)

2 files, +27 / −4, plus this ledger.

- **`src/domain/notifications/inventory.py`:** the
  `audit_finding_capa_closure` note now states the split explicitly — which
  outcome sends which type, which category owns it, and that closure is ungated
  because none does.
- **`tests/unit/test_notification_inventory.py`:** new
  `test_the_capa_closure_note_still_matches_the_category_map`, asserting
  `AUDIT_FINDING → audit_notifications` and `ACTION_COMPLETED ∉ CATEGORY_BY_TYPE`.
  The note's accuracy depends on a dict in another module that can change without
  this file being opened; the test is what makes that a failure rather than a
  quiet lie.
- **APIs / Database / Dependencies:** none. No response field changes shape; only
  the `note` string a channel/producer already carried.

## 3) Compatibility & Data Safety

- **Text and a test.** No dispatcher, route, schema or migration is touched, and
  no delivery behaviour changes. The endpoint's contract is unchanged.
- **The new test is a guard, and it is proven to bite.** With
  `NotificationType.ACTION_COMPLETED` temporarily added to `CATEGORY_BY_TYPE`,
  it fails with the message naming the note it protects; reverted immediately and
  the tree confirmed clean.
- **The residual risk is named:** this pins two mappings, not every claim in every
  note. A note asserting something about a type nobody thought to pin can still
  drift. The general fix — declaring each producer's `NotificationType`s and
  cross-checking the whole set against `CATEGORY_BY_TYPE` — is a real improvement
  and a larger change than this correction; it is stated as follow-up rather than
  smuggled in here.
- **Breaking changes:** none. **Migration plan:** N/A. **Rollback (DB):** N/A.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| `audit_finding_capa_closure` gating claim | Said category preferences can hold back the in-app push for the producer, which is false on the closure path | States which outcome is gated by `audit_notifications` and which no category owns |
| Dependency on ADMIN-03's `CATEGORY_BY_TYPE` | Asserted in prose, checked by nothing | Two mappings asserted by a test that fails if either changes |
| Bugbot finding on #1711 | Open, medium severity | Verified against source and fixed |

## 4) Acceptance Criteria (AC)

- [x] AC-01: The note names `AUDIT_FINDING`/`audit_notifications` for pending
  verification and `ACTION_COMPLETED` as owned by no category for closure.
- [x] AC-02: A test fails if `AUDIT_FINDING` stops mapping to
  `audit_notifications`, or if any category starts owning `ACTION_COMPLETED`.
- [x] AC-03: No behaviour change — no dispatcher, route, schema, migration or UI
  file touched.
- [x] AC-04: No existing test skipped, loosened, renamed or deleted.

## 5) Testing Evidence

Run in `.worktrees/notif-admin-01-inventory` on `d3c92175f` with
`/Users/davidharris/quality-governance-platform/.venv/bin/python` (3.11.15):

- [x] `pytest tests/unit/test_notification_inventory.py
  tests/unit/test_notification_inventory_route.py -q` → **62 passed, none
  skipped**.
- [x] **New test proven to bite:** `ACTION_COMPLETED` temporarily mapped to
  `audit_notifications` → `test_the_capa_closure_note_still_matches_the_category_map`
  **fails** (1 failed, 49 deselected); reverted, `git status` clean.
- [x] `mypy src/ --config-file pyproject.toml` → **Success: no issues found in 606
  source files**.
- [x] `black --check src/ tests/` → 1,417 unchanged; `isort --check-only` → clean;
  `flake8 src/ tests/` → clean.
- [x] Source facts verified directly, not taken from a ledger:
  `notify_capa_closure_bridge` selects `ACTION_COMPLETED` on
  `FindingStatus.CLOSED` and `AUDIT_FINDING` otherwise; `create_status` defaults
  `priority=MEDIUM` and `channels=[IN_APP]`; `categories_for` adds
  `high_priority_alerts` only for `HIGH`.

**Not verified:** no browser, no staging, no real delivery. Nothing here sends a
notification, and no behaviour claim is made beyond the two mappings asserted.

- [ ] Full CI — on PR.
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge).

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: An administrator reading the inventory panel sees, for the CAPA
  closure producer, a gating statement that matches the dispatcher.
- [ ] CUJ-02: Same against a deployed environment — to verify on tip after deploy.

## 7) Observability & Ops

- No new signal, log, metric or config. The corrected note is the operator-facing
  change: "why did nobody get told?" now gets a true answer for this producer
  instead of one that blames a preference toggle that cannot apply.

## 8) Release Plan

1. Open PR on tip `d3c92175f`. **Do not merge** — raised for review only.
2. Merge only after ledger / compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark conveyor **PROD → DONE**. Merge alone is not done.

## 9) Rollback Plan

- **Trigger:** the corrected note is itself shown to be wrong.
- **Rollback steps:** revert the merge commit; nothing persisted, no schema, no
  flag. The note reverts to the previous text and the guard disappears with it.
- **Owner:** Platform Engineering (Governance UX lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `fix/notif-admin-01-capa-note`
- Base: `d3c92175f` (#1711)
- Files: 2 changed, +27 / −4, plus this ledger
- Source of the finding: Bugbot review on #1711, verified independently
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — no path, parameter, request or response schema
  change; no alembic revision, no column change, no new table
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A. A documentation string and a test assertion
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] No dispatcher edit — `notification_service.py`,
  `notification_preferences.py`, `routes/notifications.py` and
  `routes/push_notifications.py` are untouched
- [x] No `Layout.tsx`, no nav, no frontend file of any kind
- [x] No alembic revision; no second head
- [x] No new permission token
- [x] No test skipped, loosened, renamed or deleted to go green
