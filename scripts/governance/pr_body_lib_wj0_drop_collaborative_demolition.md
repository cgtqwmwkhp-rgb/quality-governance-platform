# Change Ledger (CL-LIB-WJ0-DROP-COLLABORATIVE-DEMOLITION)

**Path claim:** `library/wj0-drop-collaborative` (L-35a) — demolition
**PR status:** OPEN — prep `#1692` PROD LIVE `e22b1dcee`. This is the demolition PR: sole alembic revision `20261101_lib_wj0_drop` revising `20261031_lib_wi2_homes`.
**Authority:** PEL-HSEQ-5014 v6 · enhance-never-replicate · one alembic at a time

## File allowlist (exclusive)

- `alembic/versions/20261101_lib_wj0_drop_collaborative.py` (new — sole revision)
- `alembic/env.py` (drop the `src.domain.models.collaboration` side-effect import)
- `src/domain/models/collaboration.py` (deleted)
- `src/domain/services/collaboration_service.py` (deleted)
- `tests/unit/test_collaboration_service.py` (deleted)
- `frontend/src/hooks/useCollaboration.ts` + `__tests__/useCollaboration.test.ts` (deleted)
- `frontend/src/components/collaboration/LiveCursors.tsx` (deleted)
- `frontend/src/components/realtime/CollaboratorCursors.tsx` (deleted)
- `frontend/src/hooks/index.ts`, `frontend/src/components/realtime/index.ts` (barrel exports trimmed)
- `src/api/routes/realtime.py` (module docstring only — records that the drop happened and that this router is deliberately untouched)
- `docs/governance/alembic_drift_baseline.json` (dropped tables removed)
- `docs/governance/library-wj0-drop-collaborative-inventory.md` (demolition record)
- `tests/unit/test_job_lifecycle_ux_w4.py`, `tests/unit/test_job_lifecycle_ux_w5.py` (tip-head pin advanced — see §5)
- `scripts/governance/pr_body_lib_wj0_drop_collaborative_demolition.md` (this ledger)

**Out of scope:** DocumentDetail · WI-1 CEL/standards/clauses · upload wizard · `document_graph` · Structure map · `/api/v1/realtime/*` handlers · `connection_manager` · authz allowlist · OpenAPI surface.

## 1) Summary

- **Feature / Change name:** Library WJ-0 / L-35a — DROP the `collaborative_*` CRDT trap (demolition)
- **User goal (1–2 lines):** Remove the dormant Yjs co-editing stack — tables, service, frontend hook and cursor overlays — so the WJ-1 native document editor cannot be built on a CRDT layer nobody has ever run, and cannot add a second document-body store beside one.
- **In scope:** Alembic DROP of five tables; deletion of the orphan backend and frontend modules; `alembic/env.py` import removal in the same PR as the DROP; drift baseline rewrite; inventory closed out.
- **Out of scope:** The realtime WebSocket router and `connection_manager` (in-memory notifications/presence, not CRDT) — their keep-or-cut decision is a separate slice. No `/collab` handler is added.
- **Feature flag / kill switch:** N/A. The stack was already unreachable: no route imported the service, and the frontend hook targeted `/api/v1/realtime/collab/{documentId}`, a handler that has never existed. There is nothing to flag off; the change is removal.

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Database | `collaborative_documents`, `collaborative_sessions`, `collaborative_changes`, `document_comments`, `user_presence` — created 20260120, read by nothing | All five dropped by `20261101_lib_wj0_drop` (indexes first, children before parent) |
| Backend code | `models/collaboration.py` (5 ORM classes) + `services/collaboration_service.py` (~530 lines) + ~500 lines of mocked unit tests | Deleted |
| Alembic metadata | `env.py` imported the collaboration models for autogenerate | Import removed **in this PR** — leaving it would put 5 tables in `Base.metadata` that the database no longer has, and `alembic check` fails on `CreateTableOp` |
| Frontend | `useCollaboration` (+ test), `LiveCursors`, `CollaboratorCursors`, exported from two barrels, imported by no page | Deleted; barrels trimmed |
| `/api/v1/realtime/ws\|stats\|online-users\|presence\|broadcast` | In-memory `connection_manager` | **Unchanged.** Docstring now states why the demolition did not touch it |
| Drift baseline | 1059 suppressed ops across 210 tables | 1037 across 205 — the 22 operations on the 5 dropped tables removed |
| OpenAPI / authz declarations | No collaboration paths | Unchanged — no endpoint added or removed |
| DocumentDetail / CEL / `document_graph` / Structure map | — | Untouched |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Nothing in the request path reads these tables, so there is no compatibility window to hold open. Verified by `rg CollaborationService|collaborative_|/realtime/collab` over the whole repository and by the absence of any collaboration path in `openapi-baseline.json`.
- **Breaking changes:** None reachable by a user. Five tables that no code path reads are removed.
- **Data safety / row counts:** Production row counts **could not be queried** — the authoring environment has no operator access to the production database, and the prep PR could not obtain them either. Rather than assert a count nobody measured, the migration logs `SELECT COUNT(*)` for each table at `INFO` immediately before dropping it, so the deploy log records exactly what was destroyed. The drop is unconditional on purpose: any row present is abandoned CRDT state for a feature that was never reachable from any route, there is no migration path from a Yjs blob to the native editor, and a migration that refused on a non-empty table would wedge the deploy on data nobody can act on.
- **Sibling decision (`document_comments`, `user_presence`):** dropped with the stack. `document_comments` has no route, service caller or frontend consumer, and the live commenting need is already served by `document_discussion_threads` / `document_discussion_messages` (`governed_knowledge.py`, wired to `/api/v1/governed-knowledge`) — keeping an unread second comment table beside a read one is exactly the duplicate SoT the anti-dupe plan forbids. `user_presence` is not what `/api/v1/realtime/presence/{user_id}` reads; that route answers from the in-memory `connection_manager` and always has.
- **Migration:** one revision, `20261101_lib_wj0_drop`, `down_revision = "20261031_lib_wi2_homes"` (the WI-2 head that is LIVE). Sole head after merge.
- **Rollback strategy:** `alembic downgrade` recreates all five tables in exactly their pre-drop shape — the 20260120 DDL plus the `tenant_id` column and `ix_<table>_tenant_id` index that 20260308 added, with `tenant_id` in the same ordinal position ALTER TABLE left it. Verified by diffing `pg_dump --schema-only` of the downgraded database against a reference database built to `20261031_lib_wi2_homes`: identical. Schema only — the rows do not come back.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CRDT / `collaborative_*` trap (L-35a) | Five dormant tables, an orphan service and three orphan UI modules | Removed; WJ-1 native editor has no CRDT layer to inherit |
| Duplicate SoT (document comments) | `document_comments` (unread) beside `document_discussion_*` (read) | Single wired discussion SoT |
| Alembic serialisation | WI-2 `20261031_lib_wi2_homes` LIVE and free | One revision on top of it; single head |
| Autogenerate honesty | 5 tables in `Base.metadata` with drift baselined against them | Tables and their 22 baselined operations both gone; ratchet still passes |
| Realtime keep-set | Undecided | Still undecided, and explicitly untouched — recorded in the inventory as open |

## 4) Acceptance Criteria (AC)

- [x] AC-01: Single alembic revision `20261101_lib_wj0_drop` with `down_revision = "20261031_lib_wi2_homes"`; it is the only head
- [x] AC-02: `collaborative_changes`, `collaborative_sessions`, `collaborative_documents` dropped, indexes first, children before the parent they reference
- [x] AC-03: `document_comments` + `user_presence` dropped, with the keep-or-cut reasoning written down rather than assumed
- [x] AC-04: No edits to DocumentDetail, CEL/standards/clauses, upload wizard, `document_graph` or Structure map
- [x] AC-05: `/api/v1/realtime/ws|stats|online-users|presence|broadcast` unchanged; no `/collab` handler added; authz declarations and OpenAPI baseline unchanged
- [x] AC-06: Orphan code deleted — `CollaborationService`, the collaboration models, their unit tests, `useCollaboration` (+ test), `LiveCursors`, `CollaboratorCursors`, and both barrel exports
- [x] AC-07: `src.domain.models.collaboration` removed from `alembic/env.py` in the same PR as the DROP, so `Base.metadata` and the migrated schema still agree
- [x] AC-08: `docs/governance/alembic_drift_baseline.json` updated for the dropped tables; the ratchet passes with no new-drift failure
- [x] AC-09: Downgrade recreates the exact pre-drop schema (proved by schema diff, not by inspection)

## 5) Testing Evidence

Run locally against PostgreSQL 14.20 with the repository's Python 3.11 environment.

- [x] `alembic upgrade head` — applies cleanly; all five tables absent afterwards; `alembic current` reports `20261101_lib_wj0_drop (head)`, sole head
- [x] `alembic downgrade -1` — all five tables and all 15 indexes/constraints restored
- [x] **Schema-fidelity diff:** `pg_dump --schema-only` of the downgraded database vs a reference database built to `20261031_lib_wi2_homes` — byte-identical apart from pg_dump's per-run `\restrict` nonce. This caught a real defect first time round: the recreate declared `tenant_id` second on `collaborative_sessions` / `collaborative_changes`, where history had appended it last. Fixed and re-verified.
- [x] **CI's reversibility check reproduced:** `alembic downgrade iso27001_schema_drift_02` then `alembic upgrade heads` — passes end to end, returning to `20261101_lib_wj0_drop` as sole head
- [x] `alembic check` with `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` — "No new upgrade operations detected"; 0 survive the filter; 0 `AddColumnOp`
- [x] `scripts/validate_alembic_drift_ratchet.py` — exit 0 against the rewritten baseline. Measured `AlterColumnOp=419, CreateForeignKeyOp=100, CreateIndexOp=244, DropIndexOp=204` across 205 tables, matching the rewritten baseline exactly
- [x] `pytest tests/unit` — 6292 collected, 0 collection errors, all pass (see the note below on two tip-head pins and one pre-existing local-timezone failure)
- [x] `mypy src/` — success, 599 files
- [x] `black --check src/ tests/` — 1401 files unchanged; `flake8 src/ tests/` — 0
- [x] `npx tsc --noEmit` — clean; `npx eslint src/ --max-warnings 0` — clean
- [x] `npx vitest run` — 400 files, 2746 tests, all pass
- [x] `python3 scripts/check_import_boundaries.py` and `scripts/validate_error_code_coverage.py` — both pass
- [ ] Full CI — when the PR opens
- [ ] Staging / Prod tip verify — after merge, per conveyor

**Two test edits, and why neither weakens a test.** `test_job_lifecycle_ux_w4.py` and `test_job_lifecycle_ux_w5.py` pin the name of the current alembic tip head. Their assertion is "there is exactly one head, and it is the newest revision"; the name is data the pin carries, and every migration PR advances it (`4889cd1d6` did the same for WI-2, `1a0b43172` for NS-FUNC W2). The assertion is unchanged in strength: still one head, still an exact equality, now naming `20261101_lib_wj0_drop`.

**One pre-existing failure, not fixed here.** `test_compliance_schedule_search_rbac.py::test_status_reflects_the_due_date_not_a_stored_column` fails on a clean `origin/main` (`e22b1dcee`) in this environment and passes under `TZ=UTC`. It compares `date.today()` (local) against a UTC-derived due date, so it fails only in the hour between local midnight and 01:00 BST. It is unrelated to this change and CI runs in UTC. Recorded, not fixed — that is someone else's slice.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Application boots and serves with the collaboration models absent from `Base.metadata` — `mypy src/` over 599 files and the full unit suite both import the application graph with no reference to the deleted modules; `rg` finds no residual importer anywhere in the repository
- [x] CUJ-02: Real-time notifications and presence still work — `/api/v1/realtime/ws|stats|online-users|presence|broadcast` and `connection_manager` are untouched, and `PresenceIndicator` / `NotificationCenter` still build and pass their tests (2746 frontend tests green)
- [x] CUJ-03: A deploy can be reversed — downgrade restores the pre-drop schema exactly, proved by schema diff against a reference database

## 7) Observability & Ops

- The migration logs `"<revision>: dropping <table> holding <n> row(s)"` at `INFO` for each table immediately before dropping it. That line in the deploy log is the row-count evidence this PR cannot gather in advance; read it after the production deploy.
- If a table is already absent, it logs `"<table> absent, nothing to drop"` and continues, so a partially-applied environment does not fail the deploy.
- No new metrics, dashboards or alerts. No signal is lost: nothing was ever emitted from these tables.

## 8) Release Plan

1. Open this PR; merge when CI is green (admin merge authorised; UX Functional Coverage Gate HOLD ignored per instruction)
2. `CI - Default` must be green on the merge-commit tip SHA
3. `Build, Push and Deploy to Azure` must succeed for that tip — staging first, then production
4. Verify the ACA image tag contains the tip SHA and `/healthz` returns 200 on both STG and PROD, then read the drop row counts out of the deploy log
5. Only then is WJ-0 **DONE**; WJ-1 (native editor) unblocks

## 9) Rollback Plan (Mandatory)

- **Trigger:** Migration failure on deploy, or any runtime error naming a dropped table
- **Rollback steps:**
  1. `alembic downgrade 20261031_lib_wi2_homes` — recreates all five tables in their exact pre-drop shape (schema only; CRDT rows are not recoverable, and were unreachable product state)
  2. Revert the squash merge on `main` to restore the models, the service and the frontend modules
  3. Redeploy; for a backend-only regression, `Emergency Rollback - Production` restores the previous container image first
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Inventory + demolition record: `docs/governance/library-wj0-drop-collaborative-inventory.md`
- Prep PR `#1692`, PROD LIVE `e22b1dcee` (STG=PROD, `/healthz` 200)
- WI-2 `#1691` PROD LIVE `5d1e14ec0c8` — head `20261031_lib_wi2_homes`, revised by this PR
- Anti-dupe plan: L-35a "DROP `collaborative_*` before editor"
- Conveyor: `library-spine-conveyor.canvas.tsx` slice WJ-0
- Drift baseline diff: 1059 → 1037 operations, 210 → 205 tables

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger; single alembic revision confirmed
- [x] **Gate 1:** No twin SoT — a duplicate comment table removed rather than added; no `/collab` route created
- [ ] **Gate 2:** CI green on this PR
- [x] **Gate 3:** Reversibility proved locally by schema diff; CI's own downgrade check reproduced
- [x] **Gate 4:** Data-safety position stated honestly — counts unobtainable in advance, logged at drop time
- [ ] **Gate 5:** DONE = tip LIVE on STG + PROD with `/healthz` 200 and the ACA image at the tip SHA
