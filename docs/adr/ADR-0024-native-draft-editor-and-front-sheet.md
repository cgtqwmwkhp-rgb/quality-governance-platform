# ADR-0024: Native draft editor and Front Sheet (Library WJ-1)

**Status**: Accepted — WJ-1-M1 mounted (Front Sheet live; native path awaits `content_format` in M2)  
**Date**: 2026-08-09 (proposed) · 2026-08-10 (accepted at M1)  
**Decision Makers**: David Harris (IT / business owner). Direction locked as L-14c on the Library spine 360 plan.

## Context

L-14b (“no in-app editor”) blocked Policy born→published inside QGP. The spine
360 hardening superseded that with **L-14c**:

- **Native** documents: draft-only block JSON in-app → immutable PDF at publish.
- **Binary** documents: never edited in-app — Front Sheet + replacement-on-revise.
- **Forbidden:** Office round-trip, OnlyOffice/Collabora, CRDT / `collaborative_*`.

A dormant collaborative / realtime CRDT path still exists in the tree. WJ-0 must
**DROP** that surface before any editor mounts (L-35a). Until then, this ADR
governs design only; code may land as an **unmounted package shell**.

## Decision

1. **`content_format`: `binary` | `native` (L-34).** Legacy estate defaults to
   `binary`. Conversion to `native` is a signed human act — never silent.
2. **Native block editor is draft-only (L-35).** Persist restricted JSON only.
   No HTML store. Ship as a **lazy chunk** off the App shell so size-limit stays
   green (`docs/governance/library-wj1-size-limit-notes.md`).
3. **Front Sheet for binary (L-36).** A live cover band composed from control +
   coverage (CEL). Document bytes are never mutated by the band.
4. **Render-on-publish (L-37).** Publish produces an immutable PDF artefact +
   SHA-256; Hyperlink behaviour stays uniform with Register.
5. **Draft lease + concurrency (L-38).** Single writer; logged takeover; **no
   CRDT**. Depends on WJ-0 removing collaborative_* first.
6. **Hash-chain editor events (L-39).** Mutations and leases append to
   `AuditLogEntry` (or equivalent governed audit spine) — not a second event store.
7. **Conflict ownership.** WJ-1 owns `DocumentDetail` body and version publish
   wiring **after** WB-1 layers are LIVE and WJ-0 is PROD. Prep PRs must not edit
   those paths in parallel with other Detail owners.

## Consequences

- Prep may add `frontend/src/library-editor/**` stubs + docs without mounting.
- Full WJ-1 PR must keep shell index size-limit green (editor on its own chunk /
  budget row).
- WK-1 evidence packs stay on different surfaces and may prep in parallel.
- CUT-1 retention/access converge waits for WJ-1 PROD.

## Delivery split (added at M1)

The decision landed in two slices rather than one, because decision 1
(`content_format`) needs a schema change and decisions 3 and 4 do not.

| Slice | Delivers | State |
| --- | --- | --- |
| **WJ-1-M1** | Detail body mount (lazy chunk), Front Sheet band bound to the Register row including CUT-1 retention, native draft shell with named backend gaps | Mounted |
| **WJ-1-M2** | `content_format` column + alembic (decision 1), draft block persistence (2), render-on-publish + SHA-256 (4), draft lease API (5), hash-chained editor events (6) | Outstanding |

Until M2 lands, `DocumentResponse` serves no `content_format`, so the whole
estate takes the binary path exactly as decision 1 intends for the legacy set —
conversion to native remains an act nobody has been able to perform yet, rather
than a default that happened quietly.

## Out of scope (this ADR / prep)

- DROP of `collaborative_*` (WJ-0).
- Alembic for `content_format` / lease tables (lands with implement PR after WJ-0).
- Editing `DocumentDetail.tsx` or publish paths in the scaffold PR.
- Documents list / upload wizard / document_graph.

## References

- Actions L-34…L-39 (Library spine 360).
- Conveyor slice WJ-1 — depends WJ-0 PROD; PR rule: editor chunk; no Documents list.
- Scaffold package: `frontend/src/library-editor/`.
