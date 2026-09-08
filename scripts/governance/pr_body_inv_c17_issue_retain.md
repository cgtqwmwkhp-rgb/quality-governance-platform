# Change Ledger (CL-INV-C17-ISSUE-RETAIN)

> Adjacent, not fixed here: leftover `contributing_factors` text and leftover
> flat-key readers stay until C18 (held). ICAM factor CRUD (C12) and pack draw
> internals (C15/C16) are untouched except that generate excludes retained
> issued PDFs from the next pack's evidence list. Kill SHA is C16 LIVE
> `32169460f96c`. Azure stays one merge SHA.

## 1) Summary
- **Feature / Change name:** INV-C17 — gate issue and retain the PDF (DEC-4 + DEC-5)
- **User goal:** Generating a pack is not issuing it. An external pack may only
  be issued when the investigation is complete and a human has cleared the
  redaction review. At issue the PDF is rendered once, checksummed, stored in
  the existing evidence library, and named on a disclosure log. Later download
  of that pack returns those bytes, not a live re-render.
- **In scope:** additive pack columns + `investigation_pack_disclosures`;
  review and issue endpoints; download serves retained bytes after issue;
  Report-tab review/issue controls (plain English on the lazy chunk); OpenAPI
  pair; unit + frontend tests.
- **Out of scope:** C18 leftover-reader drops, ICAM editor, pack chronology
  internals, Assist triad UI, PAMS, Entra, size-limit raise, new en.json keys.
- **Feature flag / kill switch:** None. Kill SHA = C16 LIVE `32169460f96c`.

## 2) Impact Map (what changed)
- **Database:** nullable redaction-review and issued-PDF columns on
  `investigation_customer_packs`. New table `investigation_pack_disclosures`
  (`tenant_id` NOT NULL, pack, recipient, issued_at, pdf_sha256, actor).
- **Migration:** `alembic/versions/20261122_inv_c17_pack_issue_retain.py`,
  revision `20261122_inv_c17_issue`, down_revision `20261121_inv_c11_capa_why`.
  Existence-guarded upgrade; tested downgrade drops the new table and columns
  only. Retained `evidence_assets` rows are left in place (a document a
  customer was given is not a schema rollback).
- **Backend:** `investigation_pack_issue.py` owns the gate and retention.
  `POST …/packs/{id}/redaction-review`, `POST …/packs/{id}/issue`. Download
  of an issued pack reads storage and verifies SHA-256. Generate excludes
  previously retained pack assets from the next pack's evidence list.
- **Frontend:** Report tab — record redaction review and issue this pack on
  the lazy InvestigationDetail chunk as plain English.
  `investigationDetailApi.reviewCustomerPack` / `issueCustomerPack` (not the
  shell client).
- **APIs:** two new POSTs; pack list echoes review/issue facts and a
  tenant-scoped disclosure count. OpenAPI pair updated together and kept
  byte-identical. `CreateCapaFromWhyRequest` / `InvestigationFactorCreate`
  unchanged in meaning.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive expand. Packs generated before this
  revision read as "no review, never issued", which is the truth about them.
  Unissued packs still live-render on download as before.
- **External issue without review or while incomplete:** 422
  `PACK_ISSUE_BLOCKED` naming every blocker. No invented review. Nothing
  written.
- **Internal packs:** not gated. Reading the organisation's own record is
  not a customer disclosure.
- **Fail closed:** pack load is investigation + tenant. Disclosure counts
  are tenant-scoped. A missing or checksum-mismatched retained copy is 500
  with `RETAINED_PACK_*`, never a silent re-render. Tenant-less disclosure
  is refused.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** Yes. The disclosure log records who received a pack
  (name/email) and the SHA-256 of the bytes they were given. The retained
  PDF is the already-redacted pack; INV-C1 still reproduces narrative text
  as written. `contains_pii=True` on the evidence row. No new audience
  beyond the named recipient on a pack that was already generated.
- **Lawful basis / retention:** legal obligation / legitimate interest,
  existing investigation / evidence retention. Disclosure rows cascade with
  the pack. Issued PDF `evidence_assets` are left on migration downgrade.
- **New processor?** No. **New egress?** The issue act *is* the disclosure;
  it is logged rather than automated email send. **Entra?** Untouched, flag
  stays false.
- **Authorisation:** review uses `investigation:approve_customer_omit`
  (same class of act as approving a section omit). Issue uses
  `investigation:update`. Both go through `_get_investigation_or_404`.
  Cross-tenant is `TENANT_ACCESS_DENIED` / 404 before any row is written.
- **Logging:** revision events `PACK_REDACTION_REVIEWED` and `PACK_ISSUED`
  (pack uuid, audience, recipient, checksum — not pack body).

## 4) Acceptance Criteria (AC)
- [x] AC-01: External pack cannot be issued if the investigation is not
  complete (COMPLETED or CLOSED). 422, not 500.
- [x] AC-02: External pack cannot be issued if redaction review is not
  cleared. Review is never invented on the issue path.
- [x] AC-03: Internal pack may be issued without completion or review.
- [x] AC-04: Issue persists PDF bytes + SHA-256 on an `EvidenceAsset`
  (`linked_investigation_id`) in the existing library. No second blob store.
- [x] AC-05: Download of an issued pack returns the retained bytes even if
  the renderer would now differ.
- [x] AC-06: Disclosure log records recipient, time, actor, tenant, and
  checksum. Another tenant's row is not counted into this tenant's log.
- [x] AC-07: Report tab offers Record redaction review and Issue this pack
  in plain English on the lazy chunk. No new en.json keys.
- [x] AC-08: Migration is additive with a tested down script. Single alembic
  head. QGP never writes PAMS.
- [x] AC-09: OpenAPI pair records the new paths and stays byte-identical.
  Guard 4: issue/review request fields are echoed on the response. Not
  recorded in `KNOWN_UNREADABLE_REQUEST_FIELDS`.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_pack_issue.py` (gate, retain,
  download, disclosure tenant isolation, alembic up/down, Guard 4 extra
  forbid). Nearby head-pin tests updated to the new single head.
- [x] Frontend — vitest on `packIssueCopy` and InvestigationDetail Report
  tab (blockers named; review posts the review endpoint).
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incomplete investigation + cleared review → 422
  `INVESTIGATION_NOT_COMPLETE`; no upload, no disclosure row.
- [x] CUJ-02: Complete investigation + uncleared review → 422
  `REDACTION_REVIEW_NOT_CLEARED`; review is not invented.
- [x] CUJ-03: Clear review, issue to Bedford — bytes stored, checksum on
  the pack and the disclosure row; a second issue to HSE reuses the same
  bytes; download still returns the first render after the renderer is
  patched.
- [x] CUJ-04: Another tenant cannot issue or download this pack; their
  disclosure row is not counted on this tenant's list.

## 7) Observability & Ops
- **Logs:** `investigation_pack_issue_storage_*`,
  `investigation_pack_retained_download_failed`,
  `investigation_pack_retained_checksum_mismatch`.
- **Metrics:** none new.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green.
  C18 stays held. Azure is one SHA.
- After deploy: `build_sha` on prod equals this merge SHA; generate an
  external pack, refuse issue until review + complete, then issue and
  confirm download bytes match the retained checksum.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** an external pack is issued without a cleared
  review; download of an issued pack returns a live re-render; a disclosure
  row from another tenant is visible on this tenant's list.
- **Rollback steps:** Revert the squash; redeploy C16 `32169460f96c`.
  Existing disclosure rows and issued-PDF columns are ignored by the older
  image. Retained evidence assets remain in the library.
- **Owner:** David Harris

## 10) Evidence Pack
- Kill SHA: `32169460f96c` (INV-C16 LIVE)
- Head at open: `32169460f96c`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Additive migration; review + issue endpoints; retained
  download; Report-tab controls; OpenAPI pair byte-identical
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
