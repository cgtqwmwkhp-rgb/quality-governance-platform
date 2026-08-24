# WJ-1 design note — Native draft editor + Front Sheet

**Status:** M1 mounted (Front Sheet live on Detail); M2 outstanding  
**Date:** 2026-08-09 (prep) · 2026-08-10 (M1)  
**Programme:** Library AUTH lane · conveyor WJ-1 (L-34…L-39)  
**ADR:** [ADR-0024](../adr/ADR-0024-native-draft-editor-and-front-sheet.md)

## Absolute rules

1. **WJ-0 before mount.** DROP `collaborative_*` / CRDT trap first (L-35a).
2. **No DocumentDetail race.** WB-1 shipped layers; WJ-1 owns Detail body later —
   prep = **new files only**.
3. **L-14c stance.** Native = block JSON draft → render immutable PDF. Binary =
   Front Sheet + replace-on-revise. No Office round-trip.
4. **Shell size-limit green.** Lazy chunk; see
   `library-wj1-size-limit-notes.md`.

## What M1 ships (mounted)

| Artefact | Path | Purpose |
| --- | --- | --- |
| Lazy body entry | `…/DocumentBodyPanel.tsx` | The one production entry; picks the body per L-34 |
| Format decision | `…/contentFormat.ts` | Binary vs native, with the reason it chose |
| Front Sheet band | `…/FrontSheetBand.tsx` | L-36 live cover from the Register row |
| Front Sheet model | `…/frontSheetModel.ts` | Register row → band; missing stays missing |
| Retention display | `…/retentionDisplay.ts` | CUT-1 `(years, anchor, basis)` made readable |
| Native draft shell | `…/NativeDraftEditorShell.tsx` | L-35 blocks, read-only, with named backend gaps |
| Detail mount | `frontend/src/pages/DocumentDetail.tsx` | `lazy(() => import(...))` at the top of Control |
| Size-limit row | `frontend/.size-limit.json` | Measured 3.9 kB gzip, 6 kB ceiling |
| Vitest | `…/__tests__/libraryEditorPackage.test.tsx`, `…/libraryEditorHelpers.test.ts`, `pages/__tests__/DocumentDetailBodyMount.test.tsx` | Mount, honesty, and the static-import guard |

**Where the estate lands today.** `DocumentResponse` has no `content_format`, so
every filed document takes the binary path and gets the Front Sheet. The native
branch is reachable, tested, and activates the day the API answers `native` —
which is M2, because the column needs an alembic revision this slice does not own.

## Deferred to M2 (+ later)

- `content_format` column + alembic; conversion as a signed act (L-34)
- Draft block persistence — no endpoint stores block JSON today (L-35)
- Draft lease API + takeover audit (L-38)
- Version publish → render-on-publish PDF + SHA-256 (L-37)
- Hash-chain editor events on AuditLogEntry (L-39)
- CEL coverage composition for the band's Coverage line
- Any touch of `collaborative_*`, realtime FE, WI-1 CEL, WI-2 file homes,
  `document_graph`, Documents list/upload

## Exit for implementers

- [x] WJ-0 PROD verified (collaborative_* gone).
- [x] Detail mount is a dynamic import, guarded by a test that reads the source.
- [x] Size-limit row for editor chunk; shell index gzip unchanged.
- [x] Binary path shows Front Sheet; native path shows the draft shell.
- [ ] Publish immutable (L-37) — publish still runs from the History layer and
      produces no rendered PDF artefact. M2.
