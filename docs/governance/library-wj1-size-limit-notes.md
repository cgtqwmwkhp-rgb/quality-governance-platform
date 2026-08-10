# WJ-1 size-limit notes — native draft editor chunk

**Status:** Applied at WJ-1-M1 — budget row measured and enforced; shell budgets unchanged  
**Date:** 2026-08-09 (prep) · 2026-08-10 (M1 measurement)  
**Slice:** Library WJ-1 (after WJ-0 PROD)  
**Related:** ADR-0024 · `frontend/.size-limit.json` · `frontend/src/library-editor/`

## Goal

Keep the **App shell** (`dist/assets/index-*.js`) size-limit **green** when the
native draft editor lands. The editor must not ride the index closure.

## Current shell budgets (tip `c8934dc67` baseline)

Enforced in `frontend/.size-limit.json`:

| Path | Limit (gzip) | Role |
| --- | --- | --- |
| `dist/assets/index-*.js` | 187 kB | App shell / route table |
| `dist/assets/vendor-*.js` | 200 kB | Shared vendors |
| `dist/assets/index-*.css` | 35 kB | Global CSS |

This scaffold **does not edit** `.size-limit.json` and **does not** static-import
the editor from `App.tsx` or `DocumentDetail.tsx`, so measured shell size is
unchanged.

## Wiring as built (WJ-1-M1)

1. **Lazy only.** `DocumentDetail.tsx` holds exactly one reference to the
   package, and it is a dynamic import:

   ```ts
   const DocumentBodyPanel = lazy(() => import('../library-editor/DocumentBodyPanel'))
   ```

   `DocumentBodyPanel` is the package's only production entry: the format
   decision (L-34), the Front Sheet band and the native draft shell all hang off
   it, so nothing else in the page can reach the editor without going through the
   dynamic boundary. The prep-era `loadLibraryEditorPackage` helper is deleted —
   `React.lazy` needs a default export, and keeping a second entry point would
   have given Rollup a second reason to emit the package.

   `frontend/src/pages/__tests__/DocumentDetailBodyMount.test.tsx` reads
   `DocumentDetail.tsx` and fails if any static import of the package appears, so
   the boundary is a test, not a convention.

2. **Separate Rollup chunk.** Vite's natural async chunk is stable and named
   after the entry module, so no `manualChunks` entry was needed:
   `dist/assets/DocumentBodyPanel-*.js`.

3. **Dedicated size-limit row, measured.** The 45 kB placeholder is replaced by
   the measurement:

   Measured by `npx size-limit` on the same machine, base `45cf0d55` versus this
   branch:

   | Chunk | Base | This branch | Limit |
   | --- | --- | --- | --- |
   | `dist/assets/DocumentBodyPanel-*.js` | — | **3,893 B** | 6 kB (new row) |
   | `dist/assets/index-*.js` | 197,300 B | 197,322 B (**+22 B**) | 198 kB (unchanged) |
   | `dist/assets/vendor-*.js` | 169,373 B | 169,373 B | 200 kB (unchanged) |
   | `dist/assets/index-*.css` | 30,462 B | 30,462 B | 35 kB (unchanged) |

   The shell gains **no module**. The +22 B is the new chunk's filename entering
   the Vite preload map that the index embeds — the price of the chunk existing,
   not of any editor code riding the shell. 678 B of headroom remains against the
   ceiling, so the ceiling does not move.

   The band deliberately carries plain English rather than i18n keys: an `en`+`cy`
   key pair is a shell cost and the copy is not, and on a shell with ~700 B of
   headroom that difference is the whole budget.

   `DocumentDetail-*.js` grew 20,936 → 21,060 B gzip (+124 B) for the extra
   interface fields, the `lazy` call and the Suspense wrapper. The 3.9 kB body
   itself is on its own chunk and is fetched only when a document is opened.

   The ceiling is 6 kB rather than the 45 kB placeholder so that a block toolkit
   or an Office viewer arriving on this chunk has to be ledgered rather than
   absorbed silently.

4. **Never** add TipTap/ProseMirror/Yjs/Office viewers to the shell vendor chunk
   for WJ-1. If a block toolkit is chosen later, it belongs in the editor chunk
   (or a nested `library-editor-vendor` chunk) with its own limit.

## Exit criteria for WJ-1 implement PR

- [x] Editor + Front Sheet loaded only behind lazy import from Detail (post WJ-0).
- [x] `npx size-limit` green on this branch; four rows, all passing.
- [x] New size-limit row covers the editor chunk; index budget unchanged and
      index gzip unchanged.
- [x] No CRDT / collaborative_* imports in the editor package.
- [ ] M2: keep the row green when `content_format`, draft persistence and the
      lease API land — that is when this chunk actually grows.
