# WJ-1 size-limit notes — native draft editor chunk

**Status:** Prep notes (do **not** raise shell budgets in this scaffold)  
**Date:** 2026-08-09  
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

## Required wiring (implement PR, post WJ-0)

1. **Lazy only.** Mount via dynamic import, e.g.

   ```ts
   const loadEditor = () => import('../library-editor')
   // or
   import { loadLibraryEditorPackage } from '../library-editor/loadLibraryEditorPackage'
   ```

2. **Separate Rollup chunk.** Prefer Vite’s natural async chunk for
   `library-editor` (chunk name will look like `library-editor-*.js` or a hash).
   Optional: add an explicit `manualChunks` entry keyed on
   `LIBRARY_EDITOR_CHUNK_ID` / path contains `library-editor` if the async chunk
   is unstable across builds.

3. **Add a dedicated size-limit row** when the chunk first appears in `dist/`,
   for example:

   ```json
   {
     "path": "dist/assets/library-editor-*.js",
     "limit": "45 kB",
     "gzip": true,
     "name": "library-editor: WJ-1 native draft + Front Sheet (lazy; not in index)"
   }
   ```

   Adjust the path glob to match the actual Vite output once measured. Starting
   budget **45 kB gzip** is a placeholder — replace with measured CI evidence
   before merge; raise only with a Change Ledger justification (same pattern as
   prior index bumps).

4. **Never** add TipTap/ProseMirror/Yjs/Office viewers to the shell vendor chunk
   for WJ-1. If a block toolkit is chosen later, it belongs in the editor chunk
   (or a nested `library-editor-vendor` chunk) with its own limit.

## Scaffold proof

| Check | Expectation |
| --- | --- |
| `frontend/src/library-editor/**` exists | Package shell + Front Sheet stub |
| No import from `DocumentDetail.tsx` / `App.tsx` / `Documents.tsx` | Conflict avoidance |
| Vitest imports package in tests only | Does not affect production `index-*.js` |
| `.size-limit.json` untouched in prep | Shell stays at 187 / 200 / 35 |

## Exit criteria for WJ-1 implement PR

- [ ] Editor + Front Sheet loaded only behind lazy import from Detail (post WJ-0).
- [ ] `pnpm size-check` (or CI performance-budget) green on tip.
- [ ] New size-limit row covers the editor chunk; index budget unchanged unless
      a measured, ledgered shell delta is unavoidable (prefer zero shell delta).
- [ ] No CRDT / collaborative_* imports in the editor package.
