# Change Ledger (CL-LIB-NS-EXP-CASCADE-AGGREGATE)

## 1) Summary

- **Feature / Change name:** Library Northern Star W8 / NS-EXP — cascade
  aggregate API + Structure map L1–L5 explorer + IMS052 Parent PEL
- **User goal (1–2 lines):** An operator opens **Structure map** and explores
  the estate by cascade level (L1–L5) from one aggregate request, and IMS052
  export shows each document's confirmed Parent PEL.
- **In scope:**
  - `GET /api/v1/document-graph/cascade` — readable documents + confirmed
    `implements` edges + band counts + workbook orphan ids
    (`DocumentGraphService.get_cascade_aggregate`), gated by master
    `document_graph`.
  - `frontend/src/pages/DocumentStructureMap.tsx` — consume the aggregate once
    (no 1+N edge fan-out); L1–L5 band filter chips; level + Parent PEL on the
    picker.
  - IMS052 fixed column contract gains **Parent PEL** after **Level**, filled
    only from a confirmed primary-parent `implements` edge.
- **Out of scope (deferred, see §3):** dedicated orphan board UI / Confirm Queue
  twin, Function-scoped pyramid filter query param, regenerating
  `docs/contracts/openapi.json`, DocumentDetail body edits, any flag flips.
- **Feature flag / kill switch:** Master `DOCUMENT_GRAPH_ENABLED` /
  client `document_graph` (route 404s when closed). Structure map chrome still
  requires `document_graph_structure_map`. No new flags. Visible when WE-1
  flags are already on (W7 LIVE).

## 2) Impact Map (what changed)

- **Frontend:** Structure map loads `documentGraphApi.getCascade()` once; band
  toolbar + level/parent chrome on the existing `/documents/structure` page.
  Helpers in `documentStructureMapHelpers.ts`; client types + `getCascade` in
  `documentGraphClient.ts`. No new route, page, or nav entry.
- **Backend:** `DocumentGraphService.get_cascade_aggregate`; additive schemas;
  additive `GET /cascade` route. IMS052 `build_register_row` /
  `build_document_register_rows` resolve Parent PEL from confirmed primary
  parent edges.
- **APIs:** `GET /api/v1/document-graph/cascade` (additive). Requires
  `document:read`. Returns documents, edges, bands, orphans.
- **Database:** None.
- **Config/env/flags:** None (reuses WE-1 governed Doc Graph flags).
- **Dependencies:** None.
- **Tests:** `tests/unit/test_document_graph_ns_exp_cascade.py`; extended
  `tests/unit/test_document_register_export.py`; FE Structure map + helpers +
  client tests updated for the aggregate path.
- **Docs:** This Change Ledger.
- **Contract baseline:** One added path and four added schemas; nothing existing
  removed (`check_openapi_compatibility.py` run below). IMS052 column contract
  is intentionally extended (Parent PEL) — pinned by updated unit tests.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive API + FE switch to the aggregate. IMS052
  column order gains one column after Level (evidence-pack contract update for
  W8 / CAS-3). Parent PEL is blank when no confirmed primary parent exists —
  never invented from Implements/Supported-by prose.
- **Breaking changes:** Downstream consumers that hard-coded the previous 16
  IMS052 columns must accept the 17th (**Parent PEL**). This is the planned W8
  split from the Northern Star master plan (`document_register_export`: W3 Level
  · W8 Parent).
- **Migration plan:** No migration.
- **Rollback strategy (DB):** Not applicable. Code rollback removes the route /
  restores prior Structure map behaviour by reverting the PR.

### Honest deferrals

| Concern | State after this PR |
| --- | --- |
| Orphan *board* UI | **Deferred.** Aggregate returns workbook orphan ids + counts; Structure map shows a total only. No twin orphan page. |
| Function-scoped pyramid filter | **Deferred.** Bands are estate-wide among readable docs; Function filter can land later without a second hierarchy SoT. |
| Documents the viewer cannot read | **Omitted** from the aggregate (same as the old documents-list ACL for Structure map). Not listed with redacted titles. |
| Proposed edges on Structure map | **Still excluded.** Confirmed implements only. |
| `docs/contracts/openapi.json` | **Not regenerated.** CI compatibility check uses generated schema vs baseline. |
| Flag flips | **Not this PR.** W7 owns governed deploy of Doc Graph flags (now LIVE). |

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Structure map estate load | 1 documents page fan-out + N `listEdges` calls | One `GET /document-graph/cascade` |
| Cascade L1–L5 explorer | Hub-spoke map only; no level bands | Band chips + level badges on existing Structure map |
| Hierarchy SoT | `document_edges` | `document_edges` — unchanged |
| IMS052 Parent PEL | Absent (Level only from NS-1) | Parent PEL from confirmed primary-parent implements edge only |
| Implements/Supported-by prose as parents | Forbidden | Still forbidden |
| Doc Graph master flag closed | Structure map fetches would 404 on edges | Cascade route 404s; Structure map still issues no request when master flag off |
| Twin Documents-Cascade page | Not present | Still not present |

## 4) Acceptance Criteria (AC)

- [x] AC-01: `GET /document-graph/cascade` returns readable active documents with
  `cascade_level`, confirmed `implements` edges, L1–L5 (+ unset) band counts,
  and workbook orphan id lists/counts.
- [x] AC-02: The route 404s while `DOCUMENT_GRAPH_ENABLED` is closed; Structure
  map issues no cascade request while master or structure-map flags are closed.
- [x] AC-03: Structure map loads the estate via a single cascade request (no
  per-document `listEdges` fan-out) and can filter the picker by band without a
  second fetch.
- [x] AC-04: Parent PEL on a cascade document and on IMS052 comes only from a
  live confirmed primary-parent `implements` edge; blank otherwise.
- [x] AC-05: Restricted documents the viewer cannot read are omitted from the
  cascade aggregate (no title leak).
- [x] AC-06: Proposed / non-implements edges never appear in the cascade edges
  payload or on Structure map.
- [x] AC-07: IMS052 column contract is locked at 17 columns with **Parent PEL**
  immediately after **Level**.
- [x] AC-08: Route registration is asserted via `walk_mounted_app` (not a flat
  `router.routes` loop — WE-1 FastAPI 0.140 trap).

## 5) Testing Evidence (link to runs)

- [x] `tests/unit/test_document_graph_ns_exp_cascade.py` — 5 passed
- [x] `tests/unit/test_document_register_export.py` — 12 passed
- [x] `frontend` vitest: `documentGraphClient.test.ts` +
  `documentStructureMapHelpers.test.ts` + `DocumentStructureMap.test.tsx` —
  26 passed
- [x] `black` / `isort` clean on changed backend files; `flake8` clean
- [x] `scripts/check_openapi_compatibility.py openapi-baseline.json <generated>` —
  PASSED, additive only. Adds `/api/v1/document-graph/cascade` +
  `CascadeAggregateResponse` / `CascadeDocumentItem` / `CascadeBandSummary` /
  `CascadeOrphanSummary`. Pending-queue / issue paths in the report are baseline
  lag from earlier waves, not introduced here.
- [ ] Full CI — on PR
- [ ] Staging / Prod — tip chase after merge per conveyor

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: With Doc Graph + Structure map flags on, Structure map loads once,
  shows L2/L3 badges, Parent PEL on the child, and the relationships map for the
  focus document.
- [x] CUJ-02: Operator clicks an L3 band chip; only L3 documents remain in the
  picker; no second network call.
- [x] CUJ-03: With master Doc Graph closed, Structure map chrome may show (if
  structure flag on) but issues no cascade request; API returns 404.
- [x] CUJ-04: IMS052 row for a child with a confirmed primary parent emits the
  parent's PEL in **Parent PEL**; a root emits blank.

## 7) Observability & Ops

- Read-only aggregate — no new AuditLog events.
- Failures surface as Structure map error copy (not an empty estate).
- Kill switch remains master `DOCUMENT_GRAPH_ENABLED` (route 404 /
  `Doc Graph is not enabled in this environment.`).
- No new alert. Band counts and orphan totals are response fields for the UI,
  not new metrics.

## 8) Release Plan

1. Prerequisite met: W7 WE-1 LIVE on STG+PROD at tip
   `8ab173ce00b3d8bee037a5c5731c71441d42680d` (deploy run 31326148676;
   `/api/v1/meta/version` build_sha match; healthz 200). Doc Graph + Structure
   map flags already open via the governed path.
2. Merge this PR to `main`; `CI - Default` green on the tip SHA.
3. `Build, Push and Deploy to Azure` green for that tip SHA. No migration.
4. Verify the ACA/App Service image tag contains the tip SHA and both STG and
   PROD FQDNs are healthy (`/api/v1/healthz` 200 + `meta/version` SHA match).
5. Smoke: with flags on, open `/documents/structure` — one cascade request,
   band chips visible, Parent PEL on IMS052 export for a child with a confirmed
   primary parent.

## 9) Rollback Plan (Mandatory)

- **Trigger:** Structure map misloads the estate, band counts disagree with
  readable documents, Parent PEL appears without a confirmed primary parent,
  restricted titles leak via the aggregate, or IMS052 column consumers break on
  the 17th column.
- **Rollback steps:**
  1. Fastest partial: `gh variable set DOCUMENT_GRAPH_ENABLED --body false` (or
     `DOCUMENT_GRAPH_STRUCTURE_MAP_ENABLED`) and redeploy — cascade 404s /
     Structure map chrome closes; Register export still has Parent PEL until
     full revert.
  2. Full: revert the merge commit and let the governed CI/deploy path put the
     previous image live. No schema to unwind.
  3. Breakglass `az containerapp update` / appsettings is recovery only and must
     be followed by a workflow fix PR if the failure was infra flake.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Authority: Northern Star master plan canvas
  `library-v6-northern-star-master-plan` wave W8 (`document_graph aggregate ·
  Structure map`); cascade canvas
  `library-cascade-l1-l5-three-rounds` CAS-3
  (`GET /document-graph/cascade` before L1–L5 bands).
- ADR: `docs/adr/ADR-0021-document-relationship-graph.md` (edges SoT;
  propose→confirm); `docs/adr/ADR-0023-governance-library-reference-scheme.md`
  (no twin Documents-Cascade page).
- Prior wave LIVE: W7 WE-1 tip `8ab173ce` — STG+PROD SHA match, healthz 200,
  deploy run 31326148676.
- Spec pack: `specs/governance-library/northern-star-v6.json` (+ rules extract).
- Ledger file in repo: `scripts/governance/pr_body_lib_ns_exp_cascade.md`.
- Local evidence: unit + vitest suites listed in §5; OpenAPI compatibility
  additive-only.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger; deferrals named in §3 rather
  than implied
- [x] **Gate 1:** No twin hierarchy SoT / no twin Documents-Cascade page —
  enhance Structure map + `document_edges` only (ADR-0021 / ADR-0023)
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Behaviour verified locally — cascade unit suite, register
  export suite (Parent PEL), Structure map / helpers / client vitest, OpenAPI
  additive check; W7 LIVE prerequisite confirmed
- [x] **Gate 4:** No migration, no data change, no backfill
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed here
