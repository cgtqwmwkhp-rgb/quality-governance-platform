# Change Ledger (CL-LIB-WB1-DETAIL-360)

## 1) Summary
- **Feature / Change name:** Library SECOND belt WB-1 — Document Detail → 6 layers via entity_360 compose (L-29)
- **User goal (1–2 lines):** An HSEQ lead opening a library document sees one Detail spine with six layers (Control · Coverage · Related · Used by · History · Assurance) instead of eight tabs; Used-by composes the existing Entity360 strip + campaign results — never a second Documents-360 page.
- **In scope:** Collapse DocumentDetail tabs to six canonical layers; permanent legacy `?tab=` aliases; move Entity360Strip into Used by (single mount); Related always visible with Doc Graph off honesty; title edit under Control; FE tests; Change Ledger
- **Out of scope:** Owner column (D3); derived control status (L-02); L-12 AI Overview diet (AI Summary/Tags remain byte-identical on Control); WC-1 approval/holds; enabling `document_graph` / `entity_360`; WA-1/2/3 reopen (Register / PEL / IMS052 export); repointing cross-module `?tab=evidence` emitters
- **Feature flag / kill switch:** None new. Existing `document_graph` / `entity_360` remain default-off; layers render in both states.

## 2) Impact Map (what changed)
- **Frontend:** `DocumentDetail.tsx` (six-layer Tabs body; Entity360Strip relocated to Used by; Related honesty card; Assurance sections); `documentEvidenceTab.ts` (layers + alias map + section helpers); i18n `en.json` / `cy.json` (layer labels + Related/Used-by copy); tests `documentEvidenceTab.test.ts` + new `DocumentDetailLayers.test.tsx`
- **Backend:** None
- **APIs:** None
- **Database:** None — no Alembic
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** Vitest layer/alias/section + DocumentDetail page-level layer placement
- **Docs:** this Change Ledger
- **Contract baseline:** Unchanged (no OpenAPI)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Legacy `?tab=` values (`overview`, `evidence`, `relationships`, `versions`, `quiz`, `qa`, `watch`, `campaign-results`) permanently alias to layers. Emitters such as `documentEvidenceHref` still emit `?tab=evidence` so Knowledge Exceptions / Portal / Campaign links stay byte-stable.
- **Tolerant reader / strict writer applied?** Yes — unknown `tab` → Control; Related never redirects away when Doc Graph is off
- **Breaking changes:** UI tab labels change (eight → six). `resolveDocumentDetailTab('evidence')` now returns `'coverage'` (alias, not the old tab id). Related is always present (previously hidden when Doc Graph off).
- **Migration plan:** N/A (FE-only). Bookmarks keep working via aliases.
- **Rollback strategy (DB):** No DB change — revert the merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Detail IA (L-29) | Up to 8 tabs; no Used-by layer | Exactly 6 spine layers on Document Detail |
| Documents-360 twin | Risk of new 360 page | Forbidden — compose Entity360Strip on Detail only |
| Entity360 mount | Header strip on every Detail load | Single mount inside Used by (fetch when layer opens under real Tabs) |
| Related when Doc Graph off | Tab hidden; `?tab=relationships` redirected to overview | Layer always shown with honest not-recorded card; no edges fetch |
| Legacy deep links | Tab ids were canonical | Aliases permanent; emitters unchanged in WB-1 |
| WA-1/2/3 surfaces | LIVE | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01 (L-29): Exactly six triggers render in order Control · Coverage · Related · Used by · History · Assurance with both flags off and both on — no seventh trigger
- [x] AC-02: Legacy `?tab=` values resolve per the alias table; unknown/absent → `control`; `?tab=campaign-results&campaignId=9` opens Used by with campaign 9 selected
- [x] AC-03: `?tab=evidence` opens Coverage and keeps `proposed-evidence-links` scroll contract; `?tab=qa` / `?tab=watch` / `?tab=quiz` open Assurance with section anchors
- [x] AC-04: `Entity360Strip` mounts exactly once inside Used by; no Documents-360 route added
- [x] AC-05: With `document_graph` off, Related shows the honesty card and issues no edges request; `?tab=related` / `?tab=relationships` do not redirect to Control
- [x] AC-06: With `entity_360` off, Used by still renders campaign-results compose — layer never blank
- [x] AC-07: FE Vitest covers layers/aliases/sections + DocumentDetail placement; no backend / OpenAPI / migration in this PR

## 5) Testing Evidence (link to runs)
- [x] `vitest` `documentEvidenceTab.test.ts` + `DocumentDetailLayers.test.tsx` — 20 passed (local)
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: HSEQ lead opens a document and walks Control → Coverage → Related → Used by → History → Assurance — every prior panel is reachable; nothing orphaned
- [x] CUJ-02: Operator follows a pre-WB-1 bookmark `/documents/:id?tab=evidence` and lands on Coverage at proposed evidence links
- [x] CUJ-03: Staff opens `/documents/:id?tab=qa` and lands on Assurance at the Q&A section
- [x] CUJ-04: Default tenant (flags off) opens Related, sees Doc Graph not-recorded honesty, and no edges request is issued

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None new. Entity360 fetch moves with the strip into Used by (fewer default Detail requests when real Tabs unmount inactive panels).
- **Runbook updates:** None. Flags remain default-off until a later spine-ON slice.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Ship with tip; no flag flip required for the six-layer IA.
- **Canary plan:** N/A — FE IA change; kill switch is revert.
- **DONE bar:** Conveyor marks WB-1 PROD/DONE only after tip SHA is LIVE on ACA and health is verified.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Detail navigation broken, deep-link aliases fail, or Used-by/Entity360 placement regressions.
- **Rollback steps:** Revert the merge and redeploy the prior tip. No DB rollback.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: After merge tip chase
- Canary evidence (if applicable): N/A
- Acceptance notes: L-29 from `library-world-class-ux-plan`; conveyor WB-1; compose entity_360 on Detail — never a twin 360 SoT. Adjacent held: Owner column, control status, WC-1, L-12 AI diet.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — six layers on Detail; Used-by compose; no Documents-360 twin; legacy aliases
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge; Detail layer smoke with flags off
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE before DONE
