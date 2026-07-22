# Change Ledger — Evidence Gallery

## 1) Summary
- **Feature / Change name:** Shared evidence gallery with signed image previews
- **User goal:** Replace RTA camera placeholders with real, securely served previews and reuse the evidence experience on incident and complaint records.
- **In scope:** Inline image signed URLs, shared gallery/lightbox, RTA/incident/complaint integration, frontend coverage.
- **Out of scope:** Portal metadata-only uploads remain metadata-only; portal file persistence and staff attachment workflows are unchanged.
- **Feature flag / kill switch:** N/A

## 2) Impact Map
- **Frontend:** `EvidenceGallery`, RTA Photos, Incident evidence, Complaint evidence.
- **Backend:** Evidence-asset signed URL endpoint supports validated `disposition=attachment|inline`.
- **API contract:** `GET /api/v1/evidence-assets/{asset_id}/signed-url` accepts `disposition`; only `image/*` assets receive `inline`, all other responses stay attachments.
- **Database / migrations / dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive query parameter with attachment as the default.
- **Breaking changes:** None. Existing signed URL callers retain attachment behaviour.
- **Security:** Inline disposition is restricted server-side to image content types; URLs remain tenant-scoped and time-limited.
- **Rollback strategy:** Revert this commit; no data migration required.

## 4) Acceptance Criteria
- [x] AC-01: Image thumbnails use per-asset inline signed URLs.
- [x] AC-02: Non-image evidence presents a file state and is downloadable.
- [x] AC-03: Lightbox supports next/previous controls and ArrowLeft/ArrowRight navigation.
- [x] AC-04: RTA Photos keeps upload controls and supports deletion through the shared gallery.
- [x] AC-05: Incident and Complaint evidence use the shared gallery while retaining honest loading/failure/reporter messaging.
- [x] AC-06: Attachment remains the default signed URL disposition.

## 5) Testing Evidence
- [x] Lint — `npm run lint` clean.
- [x] Frontend typecheck/build — `npm run build` clean.
- [x] Unit tests — 19 targeted frontend tests passed, including `EvidenceGallery.test.tsx` image rendering and navigation coverage.
- [x] Backend format/lint — Black and Ruff clean for `evidence_assets.py`.
- [ ] Backend tests — targeted route coverage deferred.
- [ ] Staging smoke — verify signed image preview and attachment download with tenant-scoped evidence.

## 6) Critical Journeys Verified
- [x] CUJ-01: RTA user opens uploaded scene image, navigates adjacent evidence, and deletes a photo.
- [x] CUJ-02: Incident user views linked image evidence without losing reporter-submission honesty.
- [x] CUJ-03: Complaint user sees staff-attached evidence; portal-upload metadata remains explicitly identified as metadata-only.

## 7) Observability & Ops
- **Logs / metrics / alerts:** No change.
- **Runbook:** If previews fail, confirm signed URL expiry and storage availability; download remains available as a retry path.

## 8) Release Plan
- **Staging verification:** Upload an image and document to RTA, Incident, and Complaint records; verify inline image preview, navigation, and attachment download.
- **Canary:** N/A.
- **Production checks:** Monitor browser/storage failures and confirm no non-image content is rendered inline.

## 9) Rollback Plan
- **Trigger:** Evidence previews or downloads regress.
- **Steps:** Revert the feature commit and redeploy the previous SHA.
- **Owner:** Platform team.

---

# Gate Checklist
- [x] **Gate 0:** Scope locked, acceptance criteria and Change Ledger completed.
- [x] **Gate 1:** API and UX contracts defined; inline restricted to images.
- [ ] **Gate 2:** CI green (lint, typecheck, build, tests).
- [ ] **Gate 3:** Staging verification completed with evidence.
- [ ] **Gate 4:** Canary healthy (if used).
- [x] **Gate 5:** Production verification and rollback plan documented.
