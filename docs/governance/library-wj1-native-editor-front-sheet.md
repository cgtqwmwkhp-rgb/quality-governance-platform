# WJ-1 design note — Native draft editor + Front Sheet (prep)

**Status:** Design note (Accepted direction; mount after WJ-0 PROD)  
**Date:** 2026-08-09  
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

## What this prep ships

| Artefact | Path | Purpose |
| --- | --- | --- |
| Editor package shell | `frontend/src/library-editor/` | Types, shell UI, lazy loader |
| Front Sheet band stub | `…/FrontSheetBand.tsx` | L-36 presentational cover |
| Size-limit notes | `docs/governance/library-wj1-size-limit-notes.md` | Budget plan without touching `.size-limit.json` |
| ADR-0024 | `docs/adr/ADR-0024-…` | Decision record (Proposed until implement) |
| Vitest | `…/__tests__/libraryEditorScaffold.test.tsx` | Smoke import + render |

## Deferred until WJ-0 PROD (+ implement PR)

- Mount editor / Front Sheet in `DocumentDetail.tsx`
- Version publish → render-on-publish PDF + SHA-256 (L-37)
- Draft lease API + takeover audit (L-38)
- Hash-chain editor events on AuditLogEntry (L-39)
- Alembic for `content_format` / lease columns
- Any touch of `collaborative_*`, realtime FE, WI-1 CEL, WI-2 file homes,
  `document_graph`, Documents list/upload

## Exit for implementers

- [ ] WJ-0 PROD verified (collaborative_* gone).
- [ ] Detail mount uses `loadLibraryEditorPackage` (or equivalent lazy).
- [ ] Size-limit row for editor chunk; shell green.
- [ ] Binary path shows Front Sheet; native path shows draft shell; publish immutable.
