# Change Ledger (CL-LIB-WJ1-M1-EDITOR-MOUNT-FRONT-SHEET)

**Depends:** CUT-1 `#1695` LIVE — tip `45cf0d558bd96d4bcab3936566bd61a2d7edc0b7` (MAIN = STG = PROD). WJ-0 demolition LIVE (`collaborative_*` gone). WJ-1 scaffold LIVE via `#1694` (`frontend/src/library-editor/**`, unmounted).

## 1) Summary

- **Feature / Change name:** Library WJ-1-M1 — mount the Document Detail body: Front Sheet band for binary documents, native draft shell for native ones (ADR-0024 / L-34 · L-35 · L-36), and surface CUT-1 retention where a steward can read it
- **User goal (1–2 lines):** Open a library document and see its governance cover — reference, issue, function, access, statutory and legal-hold state, and *why* it is kept until a given date — instead of a filename and a preview button. Where QGP does not know something, say so.
- **In scope:** Frontend only. Lazy Detail body mount; Front Sheet band bound to the real `DocumentResponse`; CUT-1 `retention_years` / `retention_anchor` / `retention_basis` / `retention_until` rendered with their refusals intact; native draft shell with its missing endpoints named on the page; a measured size-limit row for the new chunk; removal of the obsolete "waiting for WJ-0" copy
- **Out of scope:** `content_format` column and its alembic (M2); draft-content persistence; draft lease API (L-38); render-on-publish PDF + SHA-256 (L-37); hash-chained editor events (L-39); CUT-1c legacy retention backfill; dropping `controlled_documents.retention_period_years` (CUT-1b); the Citation flag flip (CIT-1); Documents list / upload wizard / `document_graph`
- **Feature flag / kill switch:** None. The band is read-only projection of fields the API already serves, on a route that already fetched them.

### The gap this closes

CUT-1 made retention machine-readable and its own ledger recorded the remainder honestly: *"No frontend. Retention is not yet visible to a user outside the API and the disposal queue. Surfacing it belongs with the WJ-1 Front Sheet."* This is that PR.

It also closes a smaller one. WJ-1's scaffold shipped a package that told the reader authoring was waiting on WJ-0. WJ-0 is LIVE, so that copy had become false — the only text on the page about the editor was wrong.

## 2) Impact Map (what changed)

- **Frontend — new:** `library-editor/DocumentBodyPanel.tsx` (the package's one production entry), `contentFormat.ts`, `retentionDisplay.ts`, `frontSheetModel.ts`, `formatLibraryDate.ts`
- **Frontend — rewritten:** `library-editor/FrontSheetBand.tsx` (stub fields → real Register projection), `NativeDraftEditorShell.tsx` (WJ-0 honesty copy → named backend gaps), `types.ts`, `index.ts`
- **Frontend — deleted:** `library-editor/loadLibraryEditorPackage.ts`. `React.lazy` needs a default export, and a second entry point is a second reason for Rollup to emit the package
- **Frontend — page:** `pages/DocumentDetail.tsx` — one `lazy(() => import(...))`, one `<Suspense>` at the top of the Control layer, and the Front Sheet fields added to the local row interface
- **Budgets:** `frontend/.size-limit.json` — one new row for `dist/assets/DocumentBodyPanel-*.js` at 6 kB gzip. Index, vendor and CSS ceilings untouched
- **Backend / Models / APIs / Database:** **none**. No alembic revision; no route, schema or column touched
- **Config/env/flags/Dependencies:** none
- **Tests:** `library-editor/__tests__/libraryEditorPackage.test.tsx` (renamed from `libraryEditorScaffold.test.tsx`, expanded 4 → 11), NEW `libraryEditorHelpers.test.ts` (22), NEW `pages/__tests__/DocumentDetailBodyMount.test.tsx` (6)
- **Docs:** ADR-0024 status Proposed → Accepted with an explicit M1/M2 split; `library-wj1-native-editor-front-sheet.md` and `library-wj1-size-limit-notes.md` updated from plans to as-built with measurements

### What is real and what is a stub

| Surface | State |
| --- | --- |
| Front Sheet band | **Real.** Every field is read from `GET /api/v1/documents/{id}`, which already served all of them |
| CUT-1 retention on the band | **Real.** `retention_years` / `retention_anchor` / `retention_basis` / `retention_until` as CUT-1 added them to `DocumentResponse` |
| Coverage line on the band | **Honest null.** CEL / evidence-pack composition does not exist, so the band says "not composed" rather than "none" |
| Native draft editor | **Reachable but unreached.** Renders blocks read-only. No document can be `native` today because `DocumentResponse` has no `content_format` |
| Draft save / draft lease | **Named gaps.** No endpoint serves either, so both controls are disabled and the page says which endpoint is missing |
| Version publish | **Untouched.** Publish stays on the History layer via `DocumentVersionControlBar` → `POST /api/v1/documents/{id}/publish`. This PR does not add a second publish owner to one page |
| Render-on-publish PDF + SHA-256 (L-37) | **Not built.** M2 |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive, read-only, frontend-only. No request is added, removed or reshaped; the band renders a response the page already had in hand.
- **Tolerant reader / strict writer applied?** Tolerant reader throughout, and deliberately so. Every Front Sheet field is optional in the client type because a legacy row can be missing any of them, and a missing value renders as *Not recorded* rather than as a blank cell. There is no writer: nothing in this package mutates a document, and binary bytes are never touched.
- **Breaking changes:** None. Existing Detail behaviour, layers, deep links and publish flow are unchanged; the band is added above the existing Control content.
- **Migration plan:** None. No schema change.
- **Rollback strategy (DB):** N/A — no DDL. Revert the commit and the body disappears; no data was written to roll back.

### The safety stance carried onto the page

CUT-1's invariant is that unreadable retention prose means **keep**, not destroy — a refused rule leaves `retention_until` NULL and NULL is never a disposal candidate. The band must not undo that in the presentation layer, and three rules enforce it:

1. **No inference.** A missing anchor is never defaulted to `issue`; an anchor this build does not recognise is reported as unrecognised rather than mapped to the nearest one; years with no anchor are reported as an incomplete policy rather than measured from approval.
2. **Absence is stated, not implied.** A pre-CUT-1 row with no policy says so, and says that absence means unknown rather than permission to dispose — which is exactly what deferring the CUT-1c backfill (D2) leaves behind on the estate.
3. **Disagreements are shown, not resolved.** `indefinite` and `event` policies can never produce a date. If such a row nonetheless carries one, the band shows both and names the rule as the authority instead of quietly preferring one.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| R19 retention visible to a steward | API + disposal queue only | On the document cover, with the anchor and the verbatim governance basis |
| CUT-1 refusals | Correct in the backend, invisible | Rendered as a named refusal with the reason no date exists |
| Legacy rows unbackfilled (D2) | Silent NULL | "No retention policy recorded … absence means unknown, not permission to dispose" |
| R01 identity on the cover | Reference only in the page header | PEL leads, DOC secondary, function and cascade band shown from `pel_doc_ref` |
| R26 access level | Served by the API, unrendered | Shown on the cover; read-only, so no path here can widen access |
| L-40 legal hold | Served by the API, unrendered | Flagged on the cover with its matter reference |
| L-34 binary vs native | Undecided in the UI | Decided in one total function that can never fall back to `native` |
| L-35 no HTML store / no CRDT | Scaffold only | Blocks are restricted JSON; no `collaborative_*`, Yjs, ProseMirror or Office dependency added |
| L-36 bytes never mutated | Asserted in prose | Enforced by construction — the package has no write path at all |
| Shell size-limit | 197,300 B / 198 kB | 197,322 B / 198 kB; editor on its own 3,893 B chunk with its own 6 kB row |
| One DocumentDetail owner | WB-1 owns layers | Unchanged — this PR adds a body inside the existing Control layer and edits no other layer |

## 4) Acceptance Criteria (AC)

- [x] **AC-01 (lazy mount):** The editor package is reachable from `DocumentDetail.tsx` through exactly one dynamic import and no static import, asserted by a test that reads the page source
- [x] **AC-02 (budget):** The editor lands on its own Rollup chunk with a measured size-limit row; index, vendor and CSS ceilings are unchanged and all four rows pass
- [x] **AC-03 (Front Sheet is real):** Every band field is projected from `DocumentResponse`; nothing is invented, and a field the API did not send renders as *Not recorded*
- [x] **AC-04 (CUT-1 surfaced):** A resolved policy shows years, anchor and verbatim basis; the disposal date is shown when the row has one
- [x] **AC-05 (refusals survive the UI):** A refused rule, an unknown anchor, a period with no anchor and an empty row each produce a named honest statement and never a fabricated date
- [x] **AC-06 (D2 visible):** A pre-CUT-1 row states that no policy is recorded and that absence is not permission to dispose
- [x] **AC-07 (L-34):** The body is native only when the register says `native`; the resolver is total and no unknown value can select the native path
- [x] **AC-08 (no false promises):** Draft save and draft lease are disabled and the page names the missing endpoints; no control claims a capability the backend lacks
- [x] **AC-09 (WJ-0 copy gone):** No "waiting for WJ-0" or "scaffold" copy remains on the mounted surface, asserted by a test
- [x] **AC-10 (no forbidden surface):** No `collaborative_*` import, no alembic, no Citation flag change, no `controlled_documents.retention_period_years` drop, no second publish owner
- [ ] **AC-11:** Full CI green on this SHA

## 5) Testing Evidence (link to runs)

Run locally at this SHA on Node 25.9.0 (CI uses Node 20):

- [x] `npx vitest run` — **2,785 passed / 403 files, 0 failed**
- [x] `npx vitest run src/library-editor src/pages/__tests__/DocumentDetail*` — **45 passed** (22 helper, 11 package, 6 body mount, 6 pre-existing layers suite unmodified and still green)
- [x] `npx tsc --noEmit` — clean
- [x] `npm run lint` (`eslint src/ --max-warnings 0`) — clean
- [x] `npm run build` — success
- [x] `npx size-limit` — 4/4 rows pass: index 197.32 kB / 198 kB, **library-editor 3.89 kB / 6 kB**, vendor 169.37 kB / 200 kB, CSS 30.46 kB / 35 kB
- [x] `npm run i18n:check` — 4,231 keys validated, none added by this PR
- [x] Base-vs-branch bundle measurement on the same machine, base `45cf0d55` built in a clean worktree: index gzip 197,300 → 197,322 B (**+22 B**, the new chunk's filename entering the Vite preload map — no shell module added)
- [ ] Full CI on this PR — pending
- [ ] Staging / Prod tip verify — after merge

**Not verified locally:** no browser or E2E run of the rendered band; Lighthouse CI (part of the Performance Budget job) was not run locally. Backend suites were not run because no backend file is touched by this PR.

## 6) Critical Journeys Verified (CUJ)

- [x] **CUJ-01 — Open a governed document and read its cover:** A steward opens `/documents/:id`. The Control layer lazily loads the body chunk and renders the Front Sheet: PEL lead reference with DOC secondary, issue, function, cascade band, access level, statutory and control-status badges, effective and next-review dates, and the retention policy with its basis. Covered by `DocumentDetailBodyMount.test.tsx` ("lazily mounts the Front Sheet inside the Control layer", "shows the CUT-1 retention policy the API served for this document") — which renders the real package through the page's own dynamic import rather than a mock.
- [x] **CUJ-02 — Learn why a document is kept, including when QGP cannot say:** The same steward on a document whose taxonomy rule was refused, or which predates CUT-1, is told which is the case and that no disposal date exists — never shown a plausible date. Covered by `libraryEditorHelpers.test.ts` across all eight retention states (resolved issue, supersede-while-current, event, indefinite, period-less event, unknown anchor, period with no anchor, refused rule, legacy date with no policy, empty row) and by `DocumentDetailBodyMount.test.tsx` ("renders the honest absence for a pre-CUT-1 row with no retention columns").
- [x] **CUJ-03 — Reach the native draft path without being lied to:** When the register reports `native`, the draft shell mounts instead of the band, renders blocks read-only, disables save and lease, and names the missing endpoints; publish still points at the History layer. Covered by `libraryEditorPackage.test.tsx` and `DocumentDetailBodyMount.test.tsx` ("mounts the native draft shell instead when the register says native").

## 7) Observability & Ops

- **Logs / Metrics / Alerts:** none new. The slice adds no request and no backend path, so there is nothing new to instrument; inventing a metric for a read-only projection would be noise.
- **Failure mode worth knowing:** the body is a lazy chunk on the default tab, so a chunk fetch that 404s after a deploy surfaces the existing `RouteErrorBoundary` fallback for `/documents/:id` rather than a blank page. This is the same exposure every lazy route in the app already carries; it is not made worse here, and it is why the chunk is not preloaded.
- **Runbook:** `docs/governance/library-wj1-size-limit-notes.md` records the chunk, its measurement and the rule that a block toolkit arriving on it must be ledgered rather than absorbed.

## 8) Release Plan (Local → Staging → Canary → Prod)

- Squash-merge to `main` when CI is green. Parent merges; this PR does not self-merge.
- Promote through `CI - Default` → `Build, Push and Deploy to Azure` (staging then production).
- **DONE bar:** tip SHA LIVE on STG *and* PROD with healthz 200 and the ACA image tag containing the tip SHA. Merge alone is not DONE.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** the Performance Budget job failing on the new row; the Document Detail route error boundary appearing on `/documents/:id`; any incorrect retention statement on a real document.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline deploy the reverted state. There is no database or API component to this change, so the revert is complete on its own; `Emergency Rollback - Production` restores the backend image only and would not help here, because the regression surface is frontend.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)

- CI run(s): linked once checks complete on this SHA
- Base tip: `45cf0d558bd96d4bcab3936566bd61a2d7edc0b7` (CUT-1 `#1695`), verified MAIN = STG = PROD
- Authority: ADR-0024 (accepted at M1), ADR-0023 / CUT-1, PEL-HSEQ-5014 v6, Northern Star R01 / R19 / R26 / L-34 · L-35 · L-36 · L-40
- Design notes: `docs/governance/library-wj1-native-editor-front-sheet.md`, `docs/governance/library-wj1-size-limit-notes.md`
- Depends: WJ-0 LIVE, WJ-1 scaffold `#1694` LIVE, CUT-1 `#1695` LIVE

## 11) Honest remainder (not defects introduced here)

- **No document can be native yet.** `DocumentResponse` serves no `content_format`, so the whole estate takes the binary path. The native branch is implemented and tested but unreachable in production until M2 adds the column and its alembic revision. That is the intended L-34 position for the legacy estate — conversion is a signed act nobody has been able to perform — but it does mean the draft shell ships unreached.
- **The native shell cannot save.** There is no endpoint that stores block JSON and no draft-lease endpoint. Both controls are disabled with the gap named on the page. Anything else would have been a button that throws.
- **Coverage on the band is empty by design.** CEL / evidence-pack composition is not built, so the line reads "not composed" rather than summarising nothing.
- **Legacy retention is still unbackfilled (D2).** Most filed documents will show "No retention policy recorded". That is the true state of the data, and this PR is the first place a steward can see how much of the estate is in it.
- **The band is English-only.** Every string lives in the lazy chunk rather than in `en.json` + `cy.json`, because an i18n key pair is a shell cost and the shell had ~700 B of headroom against its ceiling. Welsh coverage for the Front Sheet is a deliberate deferral, not an oversight; it should be picked up when the shell budget next has room.
- **Publish is still binary-shaped.** L-37 render-on-publish with SHA-256 is not built, so publishing a native document would publish nothing renderable. Nothing can be native yet, so this is not currently reachable — but it must land with M2, not after it.
- **UX Functional Coverage Gate** may HOLD on this PR; per the standing instruction it is not treated as a blocker for this slice.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Dependencies PROD LIVE — WJ-0 demolition, WJ-1 scaffold `#1694`, CUT-1 `#1695`; tip `45cf0d55` STG = PROD
- [ ] **Gate 2:** CI green on this SHA
- [x] **Gate 3:** No alembic revision; no `collaborative_*`; no Citation flag flip; no `controlled_documents.retention_period_years` drop; no second DocumentDetail owner and no other layer edited
- [x] **Gate 4:** No test weakened — the scaffold suite was renamed and expanded 4 → 11 with every original assertion kept or strengthened, the pre-existing `DocumentDetailLayers` suite is unmodified and green, and 39 new assertions were added
- [ ] **Gate 5:** DONE = tip LIVE on STG + PROD with healthz 200 and ACA image at tip SHA
