# Change Ledger (CL-INV-PACK-R10-ISSUED-DOCX)

> Adjacent, not fixed here: C18 leftover-reader contraction stays held. Kill SHA is
> PACK-R9 LIVE `e61888a49294`. Azure stays one merge SHA. Same stored pack payload —
> no invented narrative. Word after issue is a frozen export, not a second disclosure
> checksum and not a reopened working copy.

## 1) Summary
- **Feature / Change name:** INV-PACK-R10 — frozen Word of an issued pack from the checksummed payload
- **User goal:** After issue, a quality lead can download a Word file of what was issued, without live-editing the working copy.
- **In scope:** Retain `.docx` at first issue from the same `pack_render_payload` as the PDF; `GET …/packs/{id}/docx` serves those bytes after issue; Report-tab Word button stays available; packs issued before this PR refuse Word rather than re-render.
- **Out of scope:** C18; Entra; PAMS; `issued_docx_sha256` column; Graphik; rewriting stored sentences.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R9 LIVE `e61888a49294`.

## 2) Impact Map (what changed)
- **Database:** none. No `issued_docx_*` columns.
- **Migration:** none.
- **Backend:** `retain_issued_pdf` also writes a sibling `.docx` blob; `GET /docx` after issue reads it; missing blob is 409 `ISSUED_DOCX_UNAVAILABLE`.
- **Frontend:** Report tab Word button remains enabled after issue; copy names frozen Word vs working copy.
- **APIs:** same GET; issued path is retained bytes, not 409 `PACK_WORKING_COPY_CLOSED`.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Unissued packs still live-render the working copy. First issue renders PDF and Word from one payload, then uploads both, then records the PDF checksum. Second disclosure does not re-render. Packs issued before R10 have no Word blob and 409.
- **Fail closed:** Word render failure aborts issue before any upload. Missing issued Word blob does not live re-render.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No new fields. Word reproduces the same stored pack narrative as the PDF (C1).
- **Lawful basis / retention:** unchanged. Issued artefact remains the PDF checksum from C17. Word is a frozen convenience export at a derived storage key, not a second disclosure log.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** `investigation:update` on the Word GET. PDF download stays on the authenticated-only debt list.

## 4) Acceptance Criteria (AC)
- [x] AC-01: First issue uploads PDF and Word from the same payload. Disclosure still names `issued_pdf_sha256` only.
- [x] AC-02: After issue, Word GET returns the retained bytes. A later renderer does not change them. No `issued_docx_sha256` column.
- [x] AC-03: Unissued Word GET is still a live working copy. Second disclosure does not re-render PDF or Word.
- [x] AC-04: Issued pack with no Word blob (pre-R10) returns 409 `ISSUED_DOCX_UNAVAILABLE` and does not live re-render.
- [x] AC-05: Report tab Word stays enabled after issue and downloads frozen Word. Working-copy tooltip is not used as an edit path.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_issue.py` plus InvestigationDetail / packIssueCopy Word UI tests.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead issues a pack, then downloads Word: bytes match what was retained at issue, not a live re-render.
- [x] CUJ-02: A pack issued before this change has no Word blob; Word GET 409s; PDF download still returns the retained PDF.

## 7) Observability
- No new metrics. Missing issued Word is 409 `ISSUED_DOCX_UNAVAILABLE`. PDF retain failures stay 500.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; issue a pack and download Word; confirm a pre-R10 issued pack 409s Word.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** Issued Word is live-rendered, `issued_docx_sha256` appears, or issue succeeds without a Word blob on a new pack.
- **Rollback steps:** Revert the squash; redeploy PACK-R9 `e61888a49294`. Packs already issued under C17 keep their retained PDF bytes. Word blobs written under this PR remain at the derived key unused.

## 10) Evidence Pack
- Kill SHA: `e61888a49294` (INV-PACK-R9 LIVE)
- Head at open: `e61888a49294`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Frozen Word from the checksummed payload; working copy not reopened; no second disclosure column
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
