# ADR-0021: Document Relationship Graph (Doc Graph)

**Status**: Accepted  
**Date**: 2026-08-07  
**Decision Makers**: Product + Platform (Doc Graph P0)

## Context

Operators need a persisted document↔document relationship tracker: vertical
spines (policy → procedure → SOP / RAMS), cross-vertical peers, citation
staleness, and (later) publish-time impact. Today the platform has:

- Strong library `Document` taxonomy and ISO clause evidence via
  `ComplianceEvidenceLink` (CEL).
- A **Golden Thread** meaning already in use: controlled document → library
  document via `ControlledDocument.library_document_id`.
- No persisted typed doc↔doc graph. Semantic “related docs” are ephemeral
  search hits. `parent_document_id` is unused.

Overloading “Golden Thread” for the new graph would break existing APIs, UI
copy, and publish gating that already treat the FK as the controlled↔library
spine. Rewriting published PDF/DOCX bytes to refresh in-body hyperlinks would
violate immutability of published blobs.

## Decision

### Locked naming

| Term | Meaning |
|---|---|
| **Golden Thread** | `ControlledDocument.library_document_id` only (existing APIs / UI). |
| **Doc Graph** | Library `Document` ↔ library `Document` typed edges (+ later impact). |

UI and docs must never call Doc Graph “golden thread.”

### Nodes and edges

- **Nodes:** library `Document` only. Controlled docs participate by resolving
  through `library_document_id`.
- **Authored edge types (closed):** `implements`, `requires_record`,
  `references`, `related_to`, `conflicts_with`.
- **Derived only (lifecycle — not human-authored):** `supersedes`,
  `derived_from`.

ISO clause links stay on CEL. Doc Graph never stores clause edges. Clause
chips on a document (and any inheritance proposals through `implements`) are
**CEL read-time composition**, not Doc Graph rows.

### Immutability and citations

Never rewrite published PDF/DOCX bytes in blob storage. Citation / hyperlink
staleness is graph metadata (`cited_version`, locator, citation text) shown in
UI against the live library version.

### Propose → confirm

Mirror the CEL confirmation posture with **separate** Doc Graph status enums.
AI and heuristics may **propose** only. **No AI auto-confirm** for
impact-driving edges (`implements`, `requires_record`, `conflicts_with`, and
any edge that feeds impact propagation). Exact deterministic extractions may
land confirmed with an `extracted` method; humans confirm the rest.

### Feature flags (default off)

| Setting | Role |
|---|---|
| `document_graph_enabled` | Master gate (API 404 / UI hidden when off). |
| `document_graph_heuristic_propose_enabled` | Non-LLM proposal path. |
| `document_graph_llm_propose_enabled` | LLM proposal path (DPIA-gated later). |
| `document_graph_impact_propagation_enabled` | Publish-time impact assessments. |

### P0 prerequisites (must land before or with schema/API)

1. **CEL version pin** — evidence / clause composition reads a pinned library
   document version so Doc Graph inheritance proposals cannot silently inflate
   coverage against a moving tip.
2. **Publish hooks move** — rematch / quiz / future impact must fire on
   **publish**, not on controlled revise-draft (`gkb_publish_lifecycle` wiring).
3. **Campaign version pin** — acknowledgement campaigns bind a specific
   library/controlled version so Doc Graph impact does not cascade re-ack by
   accident.
4. **`library_document_id` fix** — stop title/reference fuzzy match as the
   SoT for controlled→library side effects; use hard FK /
   `resolve_library_for_controlled` (linked only for mutating hooks).

## Consequences

- Golden Thread semantics stay stable; Doc Graph is additive under
  `/api/v1/document-graph` and Document Detail “Relationships” (later waves).
- Published blobs remain immutable; operators see stale citations rather than
  silent byte rewrites.
- Impact and AI stay behind separate flags; Wave 0 can ship ADR + flags (+ FK
  hygiene) without enabling runtime behaviour.
- P0 follow-on PRs own CEL version pin, publish-hook move, and campaign
  version pin before impact propagation ships.

## Alternatives considered

- **Reuse “Golden Thread” for doc↔doc** — Rejected: conflicts with existing
  controlled→library FK meaning and publish denial reasons.
- **Store ISO clause links as Doc Graph edges** — Rejected: dual SoT with CEL;
  composition stays read-time.
- **Rewrite PDF hyperlinks on publish** — Rejected: breaks blob immutability
  and auditability of published versions.
- **AI auto-confirm high-confidence edges** — Rejected for impact-driving
  types; propose→confirm is the locked posture.
- **Single master flag only** — Rejected: edges must be authorable before
  impact/LLM paths open; separate flags prevent accidental blast radius.

## References

- Golden Thread link helper: `src/domain/services/gkb_control_library_link.py`
- CEL: `ComplianceEvidenceLink` / governed knowledge rematch paths
- Publish lifecycle (to wire): `src/domain/services/gkb_publish_lifecycle.py`
- Client feature catalogue: `src/domain/features/catalogue.py`
- Library PEL / function reference scheme (not Doc Graph): `docs/adr/ADR-0023-governance-library-reference-scheme.md`
- CEL harden (D15) + clause identity (D14): `docs/governance/library-cel-harden-d15.md`, `docs/governance/library-clause-identity-d14.md`
- Job axis vocabulary (sibling SSOT discipline): `docs/adr/ADR-0022-job-axis-vocabulary.md`
