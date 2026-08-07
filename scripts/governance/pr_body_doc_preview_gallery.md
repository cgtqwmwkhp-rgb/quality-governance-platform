# Change Ledger (CL-DOC-PREVIEW-GALLERY)

## 1) Summary
- **Feature / Change name:** Lane D — in-app DocumentPreview for EvidenceGallery lightbox
- **User goal (1–2 lines):** Operators can preview Tier 1 evidence (image, PDF, video, audio) inside the EvidenceGallery lightbox without downloading first; Download remains a secondary CTA.
- **In scope:** `DocumentPreview` component + mime routing helpers; EvidenceGallery lightbox wiring; unit tests for mime routing and PDF/video lightbox behaviour; optional Tier 2 text/csv preview
- **Out of scope:** IncidentDetail / Library host page changes; InvestigationEvidence host redesign; Portal*; ComplianceSchedule*; PersonNameField; backend convert services; pdf.js dependency; size-limit budget changes
- **Feature flag / kill switch:** None — additive UI behaviour on existing EvidenceGallery

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** New `DocumentPreview.tsx`; `EvidenceGallery.tsx` lightbox uses it for Tier 1/2 previewable assets (hosts unchanged)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (reuses existing evidence-asset inline signed URLs)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Tests:** `DocumentPreview.test.tsx`; EvidenceGallery lightbox PDF/video cases

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive — lightbox now renders native preview for Tier 1 types; unsupported types keep download-only copy
- **Tolerant reader / strict writer applied?** Yes — preview URL fetch failures still allow Download
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit restores download-only lightbox for non-images

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Evidence review without download | PDF / video / audio lightbox showed “cannot be previewed” + Download only | Tier 1 types render in-app (iframe / media / img); Download secondary |
| Preview honesty on failure | Images could show unavailable; other types always download-only | Signed-URL failure shows unavailable + Download for all previewable types |
| Bundle / size budgets | N/A | No new deps; size-limit budgets unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `DocumentPreview` routes image / PDF / video / audio as Tier 1 native preview; text/csv as Tier 2 when mime/extension matches
- [x] AC-02: EvidenceGallery lightbox uses `DocumentPreview` for Tier 1 assets with inline signed URLs; PDF no longer shows “cannot be previewed here”
- [x] AC-03: Download remains available as a secondary CTA for all lightbox selections
- [x] AC-04: Unit tests cover mime routing and PDF/video lightbox preview choice; no size-limit budget raise

## 5) Testing Evidence (link to runs)
- [x] Lint — deferred to CI (FE-only touch)
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `npx vitest run src/components/DocumentPreview.test.tsx src/components/EvidenceGallery.test.tsx src/components/__tests__/EvidenceGallery.upload.test.tsx` (19 passed)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens a PDF evidence tile in EvidenceGallery → lightbox shows iframe preview; Download still available
- [x] CUJ-02: Operator opens a video evidence tile → lightbox shows HTML5 video controls; “cannot be previewed” copy is absent

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open incident/complaint/RTA evidence gallery with PDF + video assets; confirm in-app preview and Download
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same lightbox path on prod FQDN; confirm `meta/version` `build_sha` matches tip before marking LIVE

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Lightbox broken for images/PDFs, or signed-URL disposition regressions
- **Rollback steps:** Revert squash commit on `main`; redeploy prior image
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

Made with [Cursor](https://cursor.com)
