# Change Ledger (CL-LIB-WJ0-DROP-COLLABORATIVE)

**Path claim:** `library/wj0-drop-collaborative` (L-35a)  
**PR status:** OPEN — prep inventory after WI-2 `#1691` PROD LIVE `5d1e14ec0c8`. Demolition (DROP + code delete) is a **separate** PR revising `20261031_lib_wi2_homes`.

## File allowlist (exclusive) — this prep commit

- `docs/governance/library-wj0-drop-collaborative-inventory.md`
- `scripts/governance/pr_body_lib_wj0_drop_collaborative.md`
- `src/domain/models/collaboration.py` (deprecation banner only)
- `src/domain/services/collaboration_service.py` (deprecation banner only)
- `frontend/src/hooks/useCollaboration.ts` (deprecation banner only)
- `frontend/src/components/collaboration/LiveCursors.tsx` (deprecation banner only)
- `frontend/src/components/realtime/CollaboratorCursors.tsx` (deprecation banner only)
- `src/api/routes/realtime.py` (comment: no `/collab` route — CRDT not productised)

**Out of scope (prep + demolition):** DocumentDetail · WI-1 CEL/standards/clauses · upload wizard · document_graph · Structure map · competing alembic heads.

**Deferred to demolition PR (not in this prep):** alembic DROP · model/service/FE deletion · drift baseline rewrite · OpenAPI/authz shrink.

## 1) Summary

- **Feature / Change name:** Library WJ-0 / L-35a — DROP `collaborative_*` CRDT trap (prep)
- **User goal (1–2 lines):** Inventory and freeze the dormant collaborative CRDT stack so WJ-1 native editor cannot land on top of it; demolition DROP is a follow-up after this prep lands LIVE.
- **In scope (prep):** Inventory + demolition checklist + Change Ledger + deprecation banners on dormant modules
- **Out of scope:** Alembic DROP; deleting tables/code; DocumentDetail editor; realtime WS gutting
- **Feature flag / kill switch:** N/A — stack already unwired (no `/realtime/collab` handler; no page consumers). Demolition removes code rather than flagging it.

## 2) Impact Map (what changed)

| Surface | Before | After (prep) |
|---------|--------|--------------|
| Docs | No L-35a inventory | `library-wj0-drop-collaborative-inventory.md` |
| Models / service / FE hooks | Dormant CRDT | Same behaviour + WJ-0 deprecation banners |
| Alembic | WI-2 LIVE; head free for next serial | **Unchanged in this PR** (DROP deferred to demolition) |
| APIs | No collab HTTP; realtime in-memory only | Comment clarifying `/collab` will not be added |
| DocumentDetail / CEL / graph | Untouched | Untouched |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Docs + comments only in prep; no schema or runtime behaviour change
- **Breaking changes:** None (prep)
- **Migration:** None in prep. Demolition DROP (pseudocode in inventory) chains after WI-1 + WI-2 heads
- **Rollback strategy:** Revert squash merge of prep commit

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CRDT / collaborative_* trap | Dormant tables + orphan service/FE | Documented demolition path; banners; no new `/collab` |
| Alembic serialisation | WI-1 `#1687` in flight | Prep adds **zero** revisions (holds DROP) |
| Native editor (WJ-1) | Blocked on WJ-0 | Prep only; WJ-1 still waits WJ-0 PROD demolition |

## 4) Acceptance Criteria (AC)

- [x] AC-01: Inventory lists `collaborative_*` (+ sibling `document_comments` / `user_presence`) tables, models, service, tests, FE, realtime relationship
- [x] AC-02: Demolition checklist includes WI-1/WI-2 alembic hold and DROP order
- [x] AC-03: No alembic file in this prep
- [x] AC-04: No edits to DocumentDetail, CEL/standards/clauses, upload wizard, document_graph, Structure map
- [x] AC-05: Change Ledger body present for future `pnpm validate:pr-body`
- [ ] AC-06: Demolition PR (separate) drops tables + deletes orphan code after WI-2 PROD — **not this prep**

## 5) Testing Evidence

- [x] Static inventory via `rg` on `origin/main` @ `c8934dc67` (worktree)
- [x] Confirmed no page consumers for `useCollaboration` / LiveCursors / CollaboratorCursors
- [x] Confirmed no `/realtime/collab` route; OpenAPI has no collaboration paths
- [ ] Full CI — when PR opened
- [ ] Staging / Prod — N/A behaviour for prep; tip chase after merge per conveyor

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Reader can execute demolition without touching WI-1 conflict paths
- [x] CUJ-02: Realtime in-memory presence routes distinguished from DB `user_presence` / CRDT tables

## 7) Observability & Ops

- None for prep
- Demolition: capture table row counts before DROP; update drift baseline

## 8) Release Plan

1. Open this prep PR (now) · merge when CI green · tip-chase LIVE
2. Follow-up demolition PR: code delete + alembic DROP + ledger AC-06 (sole alembic)
3. Merge demolition only with singular alembic head; verify tip LIVE

## 9) Rollback Plan (Mandatory)

- **Trigger:** Wrong inventory / accidental scope creep
- **Steps:** Revert merge of prep commit
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Conveyor: `library-spine-conveyor.canvas.tsx` slice WJ-0
- Anti-dupe: L-35a “DROP collaborative_* before editor”
- Inventory: `docs/governance/library-wj0-drop-collaborative-inventory.md`
- WI-2 LIVE: `#1691` tip `5d1e14ec0c8` — alembic head `20261031_lib_wi2_homes` free for WJ-0 demolition next

---

# Gate Checklist (must be complete before merge of prep)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Docs/comments only — no twin SoT tables; no alembic
- [ ] **Gate 2:** CI green (when PR opened)
- [x] **Gate 3:** N/A behaviour — verify files on tip after merge
- [x] **Gate 4:** N/A
- [ ] **Gate 5:** DONE = tip LIVE after merge (docs deploy with app tip)
