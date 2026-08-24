# Change Ledger (CL-B10-ADD-COMMENT-ANNOTATION)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `AddCommentRequest` and `AnnotationCreate` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **Depends on:** #1491 (ActionImportConfirm / ActionStatusUpdate pair)
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 38→40, open ceiling 258→256); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion; conveyor edits; gate weakening
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend:** None required for declared fields (`body`→`content` alias on comments retained)
- **Backend:** None beyond schema config
- **APIs:** Unknown fields on `POST /api/v1/investigations/{investigation_id}/comments` and `POST /api/v1/documents/{document_id}/annotations` now 422 instead of silent drop
- **Schemas/contracts:** `AddCommentRequest`, `AnnotationCreate` → `additionalProperties: false`
- **Database / workflows / config / deps:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Strict writer for these two bodies only; declared fields unchanged
- **Breaking changes:** Clients that relied on unknown fields being ignored will now get 422
- **Rollback:** Revert this PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: `AddCommentRequest` declares `extra="forbid"` and rejects unknown fields; `body` alias still maps to `content`
- [x] AC-02: `AnnotationCreate` declares `extra="forbid"` and rejects unknown fields
- [x] AC-03: Both removed from `KNOWN_LAX_WRITE_SCHEMAS`
- [x] AC-04: B-10 ratchet — **forbid ≥ 40**, **open ≤ 256**
- [x] AC-05: One open B-10 PR only; no gate weakening

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_add_comment_request_extra_forbid.py`, `tests/unit/test_annotation_create_extra_forbid.py`, ratchet updated
- [ ] CI linked after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Investigation comment with declared fields validates; unknown field raises ValidationError; `body` alias works
- [x] CUJ-02: Document annotation create with declared fields validates; unknown field raises ValidationError

## 7–10) Observability / Release / Rollback / Evidence
- Inventory markdown refreshed; staging spot-check optional unknown→422; rollback = revert PR; CI on PR checks

---

# Gate Checklist
- [x] Gate 0–1, 3–5 (schema-only)
- [ ] Gate 2: CI green

## Measured baseline (post-#1491)
| Metric | Before | After |
| --- | ---: | ---: |
| `min_forbid_count` | 38 | 40 |
| `max_open_count` | 258 | 256 |
| Schemas converted | — | `AddCommentRequest`, `AnnotationCreate` |

Made with [Cursor](https://cursor.com)
