# Change Ledger (CL-HOTFIX-GOV-LIB-CATEGORY-TREE)

## 1) Summary
- **Feature / Change name:** Hotfix — Governance Library category tree MissingGreenlet 500
- **User goal:** Restore `GET /api/v1/document-categories` so Library pickers and filters load after W0 taxonomy migrations.
- **Depends on:** Prod schema at `20260719_gov_lib_w3_review` (W0/W1/W3 applied).
- **In scope:** Avoid Pydantic `from_attributes` walking SQLAlchemy `children` relationship.
- **Out of scope:** Taxonomy content changes; FE redesign; App Service migrate-on-start (proven unsafe — alembic-before-uvicorn took prod to 503; keep ACI migration job as SSOT).
- **Feature flag / kill switch:** N/A (bugfix).

## 2) Impact Map
- **Frontend:** Library category filter/tree consumers stop receiving 500.
- **Backend:** `document_categories.py` tree builder.
- **APIs:** `GET /api/v1/document-categories` returns 200 tree.
- **Schemas/contracts:** Unchanged response shape.
- **Database:** No schema change (migrations already applied on prod).
- **Observability:** Removes recurring MissingGreenlet INTERNAL_ERROR on category tree.

## 3) Compatibility & Data Safety
- Additive behaviour fix only; nested children still assembled explicitly from flat rows.
- Prod migrations remain the existing ACI `alembic upgrade head` step in deploy-production.yml (not App Service startup).

## 4) Acceptance Criteria
- [x] AC-01: Category tree validation does not touch ORM `children` lazy relationship.
- [x] AC-02: Focused unit coverage for tree assembly without relationship IO.
- [x] AC-03: Deploy workflow keeps uvicorn-only startup (no alembic-on-start).

## 5) Testing Evidence
- [x] Unit: `pytest tests/unit/test_gov_lib_category_tree_response.py`
- [ ] CI: PR checks
- [ ] Prod: `GET /api/v1/document-categories` → 200 after tip deploy

## 6) Critical Journeys
- [x] CUJ-01: HSEQ opens Library → category filter loads sections/subcategories (no spinner forever).
- [x] CUJ-02: Taxonomy read remains available to authenticated users; inactive 06.04 hidden by default.

## 7) Rollback Plan
- **Owner:** Platform release operator
- **Rollback steps:**
  1. Redeploy prior tip SHA with `force_deploy=true`.
  2. DB stays at current head (safe); only code rolls back.

## 8) Observability & Operations
- **Metrics:** Watch 5xx rate on `/api/v1/document-categories`.
- **Logs:** MissingGreenlet on DocumentCategoryTreeNode should disappear.
- **Alerts:** Existing API 5xx alerts.
- **Runbook:** If categories 500 returns, check docker logs for greenlet/validation; confirm alembic head via ACI migrate job.

## 9) Release Plan
- **Staging:** N/A hotfix to prod tip after CI green.
- **Production:** Merge + tip force_deploy during freeze window with `force_deploy=true`.

## 10) Evidence Pack
- Unit command above; prod curl evidence after tip match.

---

# Gate Checklist
- [x] **Gate 0:** Scope lock, AC, CUJs, Change Ledger complete.
- [x] **Gate 1:** Reuses existing taxonomy APIs; no second stack.
- [ ] **Gate 2:** CI green.
- [ ] **Gate 3:** Prod evidence linked.
- [x] **Gate 4:** N/A canary (read-only API fix).
- [x] **Gate 5:** Rollback + observability documented.
