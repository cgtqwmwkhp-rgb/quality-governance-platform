# Change Ledger (CL-LIB-NS-WF-ISSUE-STATE)

## 1) Summary

- **Feature / Change name:** Library Northern Star W6 / NS-WF — issue state machine
  and the pack's issue-time hard blocks
- **User goal (1–2 lines):** A governed document goes live only by an explicit
  *issue* transition from *approved*, and only when the Northern Star rules the
  pack enforces "On issue" actually pass. Illegal status moves are refused by one
  table read from the authority pack instead of by whichever ad-hoc `if` a call
  site happened to grow.
- **In scope:** `src/domain/services/library_workflow.py` (new — the transition
  table and the R07/R10/R11/R20/R22/R23 guards), `document_library_lifecycle_service.py`
  (submit/reject/approve routed through the table; R23 version-author leg;
  new `issue_document`), `POST /api/v1/documents/{id}/issue`, two nullable
  columns on `documents` and two on `document_versions`, one Alembic revision on
  the current head, unit + integration tests.
- **Out of scope (deferred, see §3 and the gap tests):** R15 footer stamping (no
  rendering pipeline exists), the withdraw and supersede transitions (in the
  table, no endpoint), R11's date/author reconciliation against a modelled
  control block, and closing the legacy `POST /documents/{id}/publish` path.
- **Feature flag / kill switch:** None. The new endpoint is additive; every
  pre-existing path keeps its current behaviour except the two tightenings named
  in §3.

## 2) Impact Map (what changed)

- **Frontend:** None. No UI calls `/issue` yet.
- **Backend:** New `library_workflow` module; `document_library_lifecycle_service`
  now asserts every transition against the table and gains `issue_document`.
- **APIs:** `POST /api/v1/documents/{document_id}/issue` (additive). Optional body
  `{version_id?, review_cycle_months?, review_cycle_basis?}`. Requires
  `document:update`. Mirrors `/publish` for the Entity360 X-1 gate, the
  write-through to Document Control, the governed-KB publish lifecycle and the
  re-acknowledgement campaign hook.
- **Database:** `documents.review_cycle_months` (smallint, null),
  `documents.review_cycle_basis` (text, null),
  `document_versions.issued_at` (timestamptz, null),
  `document_versions.issued_by_id` (int, null, FK `users.id`).
  One revision: `20261029_lib_ns_wf_review_cycle`, `down_revision =
  20261028_lib_ns_func_ctr_svc` (the current head).
- **Config/env/flags:** None.
- **Dependencies:** None.
- **Tests:** `tests/unit/test_library_ns_wf_issue_state.py` (new, 72 cases),
  `tests/integration/test_lib_ns_wf_issue.py` (new, 4 cases). Two existing
  alembic tip-head pins advanced (`test_job_lifecycle_ux_w4/w5`), exactly as the
  precedent commit `1a0b4317` did for W2.
- **Docs:** Rationale lives in the module and migration docstrings.
- **Contract baseline:** One added path; no existing path, schema or field
  changed or removed.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive endpoint plus four nullable columns. The
  transition table was projected to match the behaviour already in the code, so
  submit/reject/approve refuse exactly what they refused before — `INDEXED` and
  `REJECTED` are declared aliases of the Northern Star *Draft* state because
  `submit_for_review` already accepted them, and `UNDER_REVISION` is deliberately
  *not* widened into Draft because it was not submittable before and that is not
  this wave's decision.
- **Breaking changes:** Two deliberate tightenings on `approve`:
  1. **R23** now also refuses the author of the *version* being approved, not
     only whoever filed the document. A user who authored revision 3 of a
     document someone else filed can no longer approve their own revision
     (`422`, code `SEPARATION_OF_DUTIES`). The pre-existing document-level
     self-approval refusal (`400`) is unchanged and still fires first.
  2. Illegal source statuses now raise the table's `StateTransitionError`
     (still `409`) with a different message string.
- **Migration plan:** `alembic upgrade head`. No backfill and no server default,
  on purpose: R20 says there is no default review cycle — it is justified by
  risk, statute or certification expectation — so writing 12 months across every
  existing row would invent exactly the justification the rule exists to demand.
  Legacy rows read as "cycle not stated" and are refused at the new issue
  transition until an owner states one. Nothing else reads these columns.
- **Rollback strategy (DB):** `alembic downgrade 20261028_lib_ns_func_ctr_svc`
  drops the four columns and the FK. Verified locally in both directions against
  PostgreSQL 16 (upgrade → downgrade → upgrade, ending at head).

### Honest deferrals

| Rule | State after this PR |
| --- | --- |
| R07 parent required | **Enforced** on issue: a document with `cascade_level > 1` needs a live, *confirmed* primary `implements` edge. Proposed edges do not satisfy it — a machine suggestion must not place a document in the cascade. |
| R10 amendment record | **Enforced** as "the version row being issued carries change notes". `DocumentVersion` *is* the amendment row; no twin `document_amendments` table was added. |
| R11 amendment reconciles | **Partially enforced**: the version leg only (the row issued is the version the document claims). The date/author leg needs a modelled control block on the document face, which does not exist. |
| R12 rows immutable | **Already enforced** by `is_immutable` + `assert_version_mutable`; pinned by a test here so it cannot rot. |
| R14 only approved versions publish | **Enforced on `/issue`.** Not enforced on the legacy `/publish`, which still reaches `PUBLISHED` from a draft. Closing it is a product decision, not a refactor: `test_library_publish_moves_the_anchored_control_record` asserts publishing must *not* invent an approval, so tightening it would mean changing a test that is currently right about its own path. The gap is asserted by a test rather than left in prose. |
| R15 level in the footer | **Not implemented and not claimed.** No rendering pipeline exists, so `issue` produces no rendition. A test asserts the absence so a future renderer cannot land silently. |
| R18 supersede same day | **Enforced** — prior issued/approved version rows and prior documents sharing the PEL reference are superseded in the same transaction as the issue, not by a nightly sweep. |
| R20 review date | **Enforced** on issue against the two new columns; the owner may state the cycle as part of the request. Nothing derives or defaults one. |
| R22 whole-number versions | **Enforced on issue only**, which is where the pack says it is enforced. Read as "zero minor" against the platform's `major.minor` scheme: `2`/`2.0` issue, `2.1` does not. It **refuses** rather than promoting `2.1` to `3` — an issued version number is printed on the document face and inventing one is the silent write the product forbids. |
| Withdraw / supersede transitions | In the table and refused-when-illegal, but no endpoint drives them yet. |
| Concurrent double-issue | **Known, not fixed.** Two simultaneous `/issue` calls can both observe `APPROVED` and both write. Every rule still runs on both, so the outcome is a duplicated issue event, not a bypassed guard. The pre-existing `approve` and `publish` paths share the same shape; fixing one path in isolation would leave the lifecycle inconsistent, so it is recorded here rather than half-closed. |

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Status moves | Ad-hoc `if` per call site, no shared table | One table projected from `northern-star-rules-v6.json`; a pack edit that renames a state fails loudly rather than quietly legalising a move |
| Going live | `/publish` straight from draft was the only route | Governed `/issue` refuses anything not already approved |
| Separation of duties (R23) | Approver compared against the document filer only | Also compared against the author of the version being approved, and re-checked at issue |
| Review cycle (R20) | Category free-text guidance only | Per-document cycle **and** basis, refused if unstated; never defaulted |
| Parent (R07) | Orphans below L1 could go live | Confirmed primary parent required before issue |
| Version numbering (R22) | Any `x.y` could be published | Issues must be whole numbers |
| Amendment record (R10/R11) | Nothing checked at publish | Change notes required and reconciled to the document version |
| Supersession (R18) | Superseded at approve only | Also superseded in the issue transaction |
| Issue attribution | `published_by_id` would have been overwritten by the issuer | Separate `issued_at` / `issued_by_id`; the approval record survives the issue |

## 4) Acceptance Criteria (AC)

- [x] AC-01: The workflow transition table is read from
  `specs/governance-library/northern-star-rules-v6.json` and never re-typed;
  every pack row that names two states is in it, and the two rows that name a
  *procedure* (level change, emergency reissue) are declared, not dropped
  silently.
- [x] AC-02: Illegal status moves are refused — including `draft → issued` and
  `under_review → issued`, the moves this wave exists to stop.
- [x] AC-03: R23 blocks approval by the author of the version being approved,
  even when a different user filed the document.
- [x] AC-04: R07 blocks issue of a `cascade_level > 1` document with no confirmed
  primary parent.
- [x] AC-05: R22 blocks issue of a decimal version and does not promote it.
- [x] AC-06: R20 blocks issue when either the cycle or its basis is unstated,
  including the half-stated case.
- [x] AC-07: `/issue` refuses a document that was never approved, and
  `version_id` cannot be used to route around the approval.
- [x] AC-08: Issue does not overwrite `published_by_id` / `published_at` — who
  approved the version survives.
- [x] AC-09: One Alembic revision on the current head, reversible, with no
  backfill and no server default.
- [x] AC-10: No rendition is produced and none is claimed (R15 gap asserted by a
  test).

## 5) Testing Evidence (link to runs)

- [x] `tests/unit/test_library_ns_wf_issue_state.py` — 72 passed
- [x] `tests/integration/test_lib_ns_wf_issue.py` — 4 passed
- [x] Full local unit suite + library integration — 6174 passed, 11 skipped,
  0 failed
- [x] `black --check` / `isort --check-only` / `flake8` on `src/` and `tests/` — clean
- [x] `mypy` on the changed modules — clean
- [x] PostgreSQL 16: `alembic upgrade head` → `downgrade -1` → `upgrade head`,
  ends at `20261029_lib_ns_wf_review_cycle`
- [x] `alembic check` with the CI filter — **0 AddColumnOp**, no new drift
- [x] `scripts/validate_alembic_drift_ratchet.py` — within baseline
- [x] `scripts.ops.run026.audit_attribution_schema` — `failures: 0`
  (`issued_by_id` is FK-constrained)
- [x] `scripts/validate_migration_naming.py` — 251 migrations, 0 violations
- [ ] Full CI — on PR
- [ ] Staging / Prod — tip chase after merge per conveyor

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: An owner issues an approved, parented, whole-numbered document that
  states its review cycle — it comes back live, the version reads `published`,
  and the approver on the version row is unchanged.
- [x] CUJ-02: An author cannot put their own work live — they cannot approve their
  own version, and an unapproved document is refused at `/issue`.
- [x] CUJ-03: An owner issuing a document with no stated review cycle is refused
  with R20 named, and may state the cycle and basis on the issue request.
- [x] CUJ-04: Every pre-existing library journey (submit, reject, approve,
  publish, revise, legal-hold refusals, Document Control write-through) behaves
  as before.

## 7) Observability & Ops

- Refusals surface through the standard error envelope with the rule id in the
  message and in `details.rule` (`R07`, `R10`, `R11`, `R14`, `R20`, `R22`, `R23`),
  so a refused issue is attributable to a named Northern Star rule in logs and in
  the client response rather than to a generic 4xx.
- Illegal transitions carry `details = {from, to, document_id}` and the existing
  `INVALID_STATE_TRANSITION` code.
- `document_versions.issued_at` / `issued_by_id` make "who put this live and
  when" a queryable fact, distinct from who approved it.
- The governed-KB lifecycle and re-acknowledgement hooks are logged and
  non-fatal on `/issue`, matching `/publish`; a failure there is visible in logs
  and does not unsay the issue.
- No new metric, dashboard or alert. Volume on a brand-new endpoint with no UI
  caller is zero on day one; adding an alert now would only assert that.

## 8) Release Plan

1. Merge to `main`; `CI - Default` green on the tip SHA.
2. `Build, Push and Deploy to Azure` green for that SHA; `alembic upgrade head`
   runs on deploy and adds four nullable columns — no lock of consequence, no
   backfill, no downtime window needed.
3. Verify the ACA image tag contains the tip SHA and the prod FQDN is healthy.
4. `/issue` is dark until a caller exists; existing journeys are unaffected.
   Nothing to enable and nothing to announce.

## 9) Rollback Plan (Mandatory)

- **Trigger:** `/issue` refuses a document that should be issuable, the tightened
  R23 leg blocks a legitimate approval, or any library lifecycle regression on
  the tip.
- **Rollback steps:**
  1. Revert the merge commit and let the governed CI/deploy path put the previous
     image live.
  2. The four added columns are nullable, unread by any other code path, and safe
     to leave in place — reverting the app alone is sufficient.
  3. Only if the schema must also go: `alembic downgrade
     20261028_lib_ns_func_ctr_svc` (verified reversible). This discards any
     review cycle and basis stated since deploy, which owners would have to
     restate.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Authority: `specs/governance-library/northern-star-rules-v6.json`
  (`workflow_transitions`, `validation_rules` R07/R10/R11/R12/R14/R15/R18/R20/R22/R23)
- Preceding waves: W4 `src/domain/services/library_rules.py` (identity blocks on
  create); this module is the "On issue" half staged in that docstring
- Precedent for the tip-head pin advance: `1a0b4317`
- Master plan canvas: `library-v6-northern-star-master-plan`, wave W6
  (`lifecycle / version · events`)

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger; deferrals named in §3 and
  asserted by tests, not only in prose
- [x] **Gate 1:** No twin SoT — `DocumentVersion` is reused as the amendment row,
  no `document_amendments` table, no `Implements → standard` edge, no Confirm
  Queue or Documents-360 surface
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Behaviour verified locally against PostgreSQL and the full test
  suite; verify on tip after merge
- [x] **Gate 4:** Migration reversible, no backfill, drift ratchet and attribution
  census clean
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed here
