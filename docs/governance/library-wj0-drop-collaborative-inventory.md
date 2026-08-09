# WJ-0 / L-35a — DROP `collaborative_*` inventory (prep)

**Status:** PREP ONLY — branch `feat/lib-wj0-drop-collaborative` · **HOLD PR** until WI-2 PROD LIVE.  
**Base tip inventoried:** `origin/main` @ `c8934dc67`  
**Depends (merge/demolition):** WI-2 PROD (conveyor serial). Prep may land earlier as docs-only.  
**Alembic:** Do **not** open a DROP migration while WI-1 `#1687` owns the next head (`20261030_lib_wi1_cel_harden_scheme`). Revise `down_revision` after WI-1 merges, then again after any WI-2 migrations.

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

Drift baseline entries: `docs/governance/alembic_drift_baseline.json` → `tables.collaborative_*`, `document_comments`, `user_presence`.

**Prod row counts:** not queried in this prep. Demolition PR must capture counts + empty/non-empty decision before DROP.

---

## 2) Backend code

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

## 5) Demolition checklist (future PR — after WI-2 PROD)

### Gate 0 — serial + evidence

- [ ] WI-1 `#1687` merged + PROD LIVE (alembic head free of competing WI-1 revision)
- [ ] WI-2 PROD LIVE (conveyor depends)
- [ ] Capture prod row counts for five tables; backup/export if non-empty
- [ ] Confirm no runtime callers via OpenAPI + `rg CollaborationService|collaborative_|/realtime/collab`

### Code removal (conflict-safe order)

- [ ] Delete or stub-fail `CollaborationService` + unit tests
- [ ] Delete FE `useCollaboration` (+ test), `LiveCursors`, `CollaboratorCursors`; trim barrel exports
- [ ] Remove `src.domain.models.collaboration` from `alembic/env.py` **in same PR as DROP**
- [ ] Decide fate of `document_comments` + `user_presence` (recommend DROP with stack unless a kept product need is documented)
- [ ] Leave `/api/v1/realtime/ws|stats|online-users|presence|broadcast` unless separately proven unused — **do not** add `/collab`

### Alembic (HOLD draft until heads settle)

```text
# Pseudocode only — do NOT land while WI-1/WI-2 migrations in flight
revision = "YYYYMMDD_lib_wj0_drop_collaborative"
down_revision = "<post-WI-2 head>"

upgrade:
  drop_index / drop_table collaborative_changes
  drop_index / drop_table collaborative_sessions
  drop_index / drop_table collaborative_documents
  # optional same PR:
  drop_table document_comments
  drop_table user_presence

downgrade: recreate from 20260120 definitions (+ tenant columns)
```

- [ ] Update `docs/governance/alembic_drift_baseline.json` exclusions/ops for dropped tables
- [ ] OpenAPI / authz declarations unchanged unless realtime endpoints removed

### Verify

- [ ] `pytest` green without collaboration unit module (or with intentional absence)
- [ ] Frontend unit/barrel imports clean
- [ ] Staging + PROD tip verify after deploy (conveyor DONE gate)

---

## 6) Gaps / open questions

1. **Sibling tables:** L-35a text says `collaborative_*` only — confirm product intent for `document_comments` + `user_presence` before DROP.
2. **Realtime keep-set:** WS presence/broadcast may still be desired for non-CRDT features; inventory found no page wiring for `useWebSocket`, but NotificationCenter exists — confirm before shrinking authz allowlist.
3. **Prod data:** row counts unknown in prep; non-empty CRDT blobs would be abandoned product state (no Office/CRDT keep path per anti-dupe plan).
4. **Alembic timing:** demolition migration must chain after WI-1 and WI-2 heads; this prep intentionally ships **zero** alembic files.

---

## 7) Prep delivered on this branch

- This inventory + demolition checklist
- Change Ledger draft: `scripts/governance/pr_body_lib_wj0_drop_collaborative.md` (**HOLD PR**)
- Deprecation banners on dormant CRDT modules (no behaviour change)
