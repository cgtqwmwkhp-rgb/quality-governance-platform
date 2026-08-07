# Change Ledger (CL-DOC-GRAPH-FLAG-PERSIST)

## 1) Summary
- **Feature / Change name:** Persist Doc Graph openers across Azure deploys
- **User goal (1–2 lines):** Keep `DOCUMENT_GRAPH_ENABLED` and `DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED` durable when staging/production deploy jobs rewrite appsettings, matching the FRA OCR / CS pattern (#1629).
- **In scope:** `deploy-staging.yml` / `deploy-production.yml` appsettings lines (API + worker/beat); `scripts/infra/env-vars.json` registry entries
- **Out of scope:** Application behaviour changes; enabling IMPACT/LLM propose; Golden Thread; SWA
- **Feature flag / kill switch:** Repo vars `DOCUMENT_GRAPH_ENABLED` / `DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED` (default false in workflow expression). IMPACT/LLM remain unwired and code-default false.

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Config/env/flags:** Deploy workflows set Doc Graph master + heuristic propose from `vars.*`; env-vars registry documents both
- **Dependencies:** None
- **Tests:** None (infra-only)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive settings keys; workflow expression defaults to `false` if var unset
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert workflow / set vars false / merge-only appsettings false

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Doc Graph opener durability | Live flip lost on next deploy | Deploy re-applies vars on each bake |
| Heuristic propose durability | Same | Same, ANDed with master in app code |
| Default posture | Code default false | Unchanged unless vars set true |
| Golden Thread conflation | Naming risk | UI/copy unchanged; flags are Doc Graph only |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Staging + production deploy workflows include both Doc Graph keys beside CS flags (API + celery)
- [x] AC-02: `scripts/infra/env-vars.json` documents both keys
- [x] AC-03: IMPACT / LLM propose remain unwired (stay code-default false)

## 5) Testing Evidence
- [ ] Lint / workflows — CI
- [x] Diff review — workflows + env-vars only

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Next prod deploy keeps Doc Graph openers true when vars are true
- [x] CUJ-02: With vars unset/false, deploy sets openers false and Doc Graph routes/UI stay closed

## 7) Observability & Ops
- **Runbook:** Flip via `gh variable set DOCUMENT_GRAPH_*` and/or `az webapp config appsettings set` (merge-only; never full PUT replace). Enable master then heuristic independently.

## 8) Release Plan
- Merge; bake opens when vars true. Live flip may precede merge for sole-operator testing.

## 9) Rollback Plan
- **Trigger:** Need Doc Graph closed
- **Owner:** Platform / David Harris
- **Steps:**
  1. `gh variable set DOCUMENT_GRAPH_ENABLED --body false` (and heuristic)
  2. Merge-only `az webapp config appsettings set … DOCUMENT_GRAPH_ENABLED=false DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED=false` on API (+ worker/beat)
  3. Never full PUT

## 10) Evidence Pack
- CI after merge

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts (deploy settings only)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Rollback via var/appsetting documented
