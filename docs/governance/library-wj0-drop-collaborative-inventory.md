# WJ-0 / L-35a — DROP `collaborative_*` inventory + demolition record

**Status:** DEMOLITION — branch `feat/lib-wj0-drop-collaborative-demolition` · prep `#1692` PROD LIVE `e22b1dcee` · this PR drops the tables and deletes the orphan code.
**Base tip inventoried:** originally `c8934dc67`; rebased onto `origin/main` @ `5d1e14ec0c8` (WI-2 LIVE); demolition branched from `e22b1dcee` (prep LIVE).
**Depends (merge/demolition):** WI-2 PROD (conveyor serial) — met. Prep landed earlier as docs-only.  
**Alembic:** demolition ships the sole revision `20261101_lib_wj0_drop`, `down_revision = "20261031_lib_wi2_homes"` (the WI-2 head that was LIVE when it was written).

**Conflict surface (allowed):** collaboration models / service / orphan FE · **not** DocumentDetail, CEL/standards/clauses, upload wizard, `document_graph`, Structure map.  
**Realtime caution:** `/api/v1/realtime/*` also serves in-memory WS presence/notifications — demolish CRDT callers only; do not gut the WS router until FE consumers are confirmed dead.

---

## 1) Database tables

| Table | Model | Created | Notes |
|-------|--------|---------|--------|
| `collaborative_documents` | `CollaborativeDocument` | `alembic/versions/20260120_tier1_enterprise_features.py` | Yjs CRDT blob + lock fields · **DROP target** |
| `collaborative_sessions` | `CollaborativeSession` | same | FK → `collaborative_documents` · **DROP target** |
| `collaborative_changes` | `CollaborativeChange` | same | FK → `collaborative_documents` · **DROP target** |
| `document_comments` | `Comment` | same | Sibling in `collaboration.py` · **not** named `collaborative_*` · decide in demolition whether to DROP with CRDT or retain for a future native-editor comment model |
| `user_presence` | `Presence` | same | Sibling · DB presence is **unused by routes** (WS uses in-memory `connection_manager`) · candidate DROP with CRDT stack |

Tenant columns added via `alembic/versions/20260308_add_tenant_id_to_all_models.py` (listed for all five).

Drift baseline entries: `docs/governance/alembic_drift_baseline.json` → `tables.collaborative_*`, `document_comments`, `user_presence`. **Removed** by the demolition PR (22 suppressed operations across 5 tables; `total_operations` 1059 → 1037).

**Sibling decision (demolition):** DROP all five. `document_comments` has no route, service caller or FE consumer, and the live commenting need is already served by `document_discussion_threads` / `document_discussion_messages` (`governed_knowledge.py`, wired to `/api/v1/governed-knowledge`) — keeping an unread second comment table beside a read one is the duplicate SoT the anti-dupe plan forbids. `user_presence` is not what `/api/v1/realtime/presence/{user_id}` reads; that route answers from the in-memory `connection_manager`.

**Prod row counts:** still not queried — the authoring environment has no operator access to the production database. Counts are therefore logged at `INFO` immediately before each `DROP` (`_log_row_count`), so the deploy log records what was destroyed. The DROP is unconditional: any row present is abandoned CRDT state for a feature that was never reachable, and there is no migration path from a Yjs blob to the native editor.

---

## 2) Backend code

*Read as the state found at inventory time. The demolition PR deletes `collaboration.py`, `collaboration_service.py` and `test_collaboration_service.py`; `realtime.py`, `connection_manager.py` and `route_declarations.py` are unchanged.*

| Path | Role | Wired to HTTP? |
|------|------|----------------|
| `src/domain/models/collaboration.py` | ORM for five tables above | Loaded by Alembic env only (`alembic/env.py` import list) · **not** exported from `models/__init__.py` |
| `src/domain/services/collaboration_service.py` | CRUD for docs/sessions/changes/comments/presence | **No route imports** — service is orphan relative to API |
| `tests/unit/test_collaboration_service.py` | Mocked unit coverage (~500 lines) | Delete / rewrite with demolition |
| `src/api/routes/realtime.py` | WS `/ws/{user_id}`, GET presence/stats/online-users, POST broadcast | Uses **in-memory** `connection_manager` — **not** `CollaborationService` / DB tables |
| `src/infrastructure/websocket/connection_manager.py` | PresenceInfo + channels | Keep until NotificationCenter / useWebSocket decision |
| `src/domain/authz/route_declarations.py` | Declares realtime routes | Trim only if endpoints removed |

**Missing route (dormant FE expects it):** FE `useCollaboration` connects to `/api/v1/realtime/collab/{documentId}` — **no such router handler exists** on main. OpenAPI baseline has no `/collaboration` or `/collab` paths. Confirms CRDT stack never productised.

---

## 3) Frontend

*State found at inventory time. The demolition PR deletes `useCollaboration` (+ test), `LiveCursors` and `CollaboratorCursors`; `useWebSocket` and `NotificationCenter` are unchanged.*

| Path | Role | Page consumers (main) |
|------|------|------------------------|
| `frontend/src/hooks/useCollaboration.ts` | WS client for collab (targets missing `/realtime/collab/...`) | **None** (export-only via `hooks/index.ts`) |
| `frontend/src/hooks/__tests__/useCollaboration.test.ts` | Hook tests | — |
| `frontend/src/components/collaboration/LiveCursors.tsx` | Cursor overlay | **None** |
| `frontend/src/components/realtime/CollaboratorCursors.tsx` | Cursor overlay | Export-only via `realtime/index.ts` |
| `frontend/src/hooks/useWebSocket.ts` | Generic `/realtime/ws/{userId}` | **No page imports found** |
| `frontend/src/components/realtime/NotificationCenter.tsx` | Notifications UI; WS line **commented out** | Confirm Layout wiring at demolition time |

No `yjs` / `y-websocket` dependency in root or frontend `package.json` / `requirements.txt` — CRDT client never landed as a dep.

---

## 4) Explicit non-targets (do not confuse)

| Surface | Why safe from WJ-0 |
|---------|--------------------|
| `investigation_comments` | Separate investigation model/routes |
| WI-1 `#1687` CEL / standards / clauses | Different files + alembic head |
| DocumentDetail / upload wizard / document_graph / Structure map | Conveyor conflict owners elsewhere |
| Realtime notification broadcast / online-users (in-memory) | Not `collaborative_*` tables — separate keep/cut decision |

---

## 5) Demolition checklist (executed by the demolition PR)

### Gate 0 — serial + evidence

- [x] WI-1 `#1687` merged + PROD LIVE (alembic head free of competing WI-1 revision)
- [x] WI-2 PROD LIVE (conveyor depends) — tip `5d1e14ec0c8` STG=PROD healthz 200
- [x] Prep `#1692` PROD LIVE — tip `e22b1dcee` STG=PROD healthz 200
- [x] Prod row counts: **not obtainable** from the authoring environment — logged at DROP time instead (see §1)
- [x] Confirm no runtime callers via OpenAPI + `rg CollaborationService|collaborative_|/realtime/collab`

### Code removal (conflict-safe order)

- [x] Delete `CollaborationService` + unit tests
- [x] Delete FE `useCollaboration` (+ test), `LiveCursors`, `CollaboratorCursors`; trim barrel exports
- [x] Delete `src/domain/models/collaboration.py` and remove `src.domain.models.collaboration` from `alembic/env.py` **in same PR as DROP** — leaving the module imported would put five tables in `Base.metadata` that the database no longer has, and `alembic check` fails on `CreateTableOp`
- [x] Decide fate of `document_comments` + `user_presence` — DROP with the stack (rationale in §1)
- [x] Leave `/api/v1/realtime/ws|stats|online-users|presence|broadcast` untouched — **no** `/collab` added

### Alembic (landed)

`alembic/versions/20261101_lib_wj0_drop_collaborative.py`

```text
revision = "20261101_lib_wj0_drop"
down_revision = "20261031_lib_wi2_homes"

upgrade:   log row count, drop indexes, drop table — children first
           collaborative_changes → collaborative_sessions → collaborative_documents
           → document_comments → user_presence

downgrade: recreate all five from the 20260120 DDL plus the 20260308 tenant_id
           column and ix_<table>_tenant_id index. Schema only; no data.
```

- [x] Update `docs/governance/alembic_drift_baseline.json` for dropped tables
- [x] OpenAPI / authz declarations unchanged — no realtime endpoint removed

### Verify

- [x] `alembic upgrade head` then `downgrade` then `upgrade` again, locally
- [x] `pytest` green with the collaboration unit module absent
- [x] Frontend typecheck / unit / barrel imports clean
- [ ] Staging + PROD tip verify after deploy (conveyor DONE gate)

---

## 6) Gaps / open questions

1. ~~**Sibling tables**~~ — closed by the demolition PR: both dropped, rationale in §1.
2. **Realtime keep-set:** still open, and deliberately untouched here. `useWebSocket` has no page wiring, but NotificationCenter exists; the WS router, `connection_manager` and the authz allowlist are unchanged by WJ-0. A separate slice owns that decision.
3. ~~**Prod data**~~ — resolved as far as it can be: counts were never obtainable from the authoring environment, so they are logged at DROP time instead of asserted in advance. Any row destroyed was abandoned CRDT state for a feature no route ever reached.
4. ~~**Alembic timing**~~ — closed: WI-1 and WI-2 are both PROD LIVE, and `20261101_lib_wj0_drop` is the sole revision in the demolition PR.

---

## 7) Delivered

**Prep (`#1692`, PROD LIVE `e22b1dcee`)**

- This inventory + demolition checklist
- Change Ledger: `scripts/governance/pr_body_lib_wj0_drop_collaborative.md`
- Deprecation banners on dormant CRDT modules (no behaviour change)

**Demolition (this PR)**

- `alembic/versions/20261101_lib_wj0_drop_collaborative.py` — sole revision
- Deleted: `src/domain/models/collaboration.py`, `src/domain/services/collaboration_service.py`, `tests/unit/test_collaboration_service.py`
- Deleted: `frontend/src/hooks/useCollaboration.ts` (+ test), `components/collaboration/LiveCursors.tsx`, `components/realtime/CollaboratorCursors.tsx`; barrels trimmed
- `alembic/env.py` no longer imports the collaboration models; drift baseline rewritten
- Change Ledger: `scripts/governance/pr_body_lib_wj0_drop_collaborative_demolition.md`
