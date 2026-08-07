# Document / evidence preview host registry (People+Preview SSOT)

**Programme:** Quality Governance Platform — People+Preview  
**Branch inventory tip:** `8596ee2c` (`feat/people-preview-registries`)  
**Agent:** INV-B  
**Generated:** 2026-08-06  

This is the single source of truth for every UI surface that previews, attempts
to preview, or opens uploaded/stored documents and evidence assets. Upload-only
surfaces with no view affordance are out of scope unless noted.

## DocumentPreview tier model (target)

| Tier | Content types | Target renderer |
| --- | --- | --- |
| **1** | Image, PDF, video, audio | Inline `<img>`, PDF iframe/object, `<video>`, `<audio>` |
| **2** | CSV, plain text, markdown | Tabular/text viewer with download fallback |
| **3** | Office (Word, Excel, PowerPoint) | Office viewer or server-side render |
| **4** | Non-visual / unknown | Metadata + download; no fake preview |

## Priority model

| Priority | Scope |
| --- | --- |
| **P0** | Shared `EvidenceGallery` component (all embedders inherit behaviour) |
| **P1** | Investigation, Action, Audit execution, Safety, UVDB/Customer audit evidence |
| **P2** | Governance Library (`Documents`, `DocumentDetail`, inline PDF) |
| **P3** | Portal intake, Planet Mark, demo/placeholder surfaces |

## Summary

| Metric | Count |
| --- | ---: |
| **Total preview hosts** | **28** |
| P0 (EvidenceGallery family) | 8 |
| P1 (case / audit / safety evidence) | 12 |
| P2 (Library) | 3 |
| P3 (portal / Planet Mark / demo) | 5 |
| Hosts at DocumentPreview tier 1 today | 6 |
| Hosts download-only or new-tab open | 14 |
| Hosts with no real file preview (placeholder / filename only) | 8 |

---

## P0 — EvidenceGallery family

### H-01 · `EvidenceGallery` (canonical component)

| Field | Value |
| --- | --- |
| **File** | `frontend/src/components/EvidenceGallery.tsx` |
| **Component** | `EvidenceGallery` |
| **Accepts / uploads** | Default: `image/*`, `video/*`, `application/pdf` (`.pdf`); max 50 MB. Overridable via `uploadAccept`, `allowedMimePrefixes`, `allowedMimeTypes`. |
| **Current preview** | **Image only.** Thumbnails + dialog lightbox via signed URL (`inline`). Non-images show `FileText` icon + MIME subtype label. Dialog copy: *"This file cannot be previewed here. Download it to view."* Download via signed URL (`attachment`). |
| **Target tier** | **Tier 1** (images ✓); **Tier 1** PDF + video + audio; retain download fallback |
| **Priority** | **P0** |

### H-02 · `CaseEvidencePanel` (EvidenceGallery wrapper)

| Field | Value |
| --- | --- |
| **File** | `frontend/src/components/case/CaseEvidencePanel.tsx` |
| **Component** | `CaseEvidencePanel` → `EvidenceGallery` |
| **Accepts / uploads** | Same defaults as H-01 (`source_module` + `source_id` via `evidenceAssetsApi.upload`). |
| **Current preview** | Delegates entirely to H-01. |
| **Target tier** | Inherit H-01 uplift |
| **Priority** | **P0** (wrapper; behaviour = H-01) |

### H-03 · IncidentDetail — Overview evidence (read-only gallery)

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/IncidentDetail.tsx` |
| **Component** | `EvidenceGallery` (`data-testid="incident-evidence-assets"`) |
| **Accepts / uploads** | Read-only (no `enableUpload`). Displays linked evidence assets. |
| **Current preview** | H-01 image-only lightbox. |
| **Target tier** | Tier 1 (+ 2–4 via shared component) |
| **Priority** | **P0** (EvidenceGallery embedder) |

### H-04 · ComplaintDetail — Evidence assets card (read-only gallery)

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/ComplaintDetail.tsx` |
| **Component** | `EvidenceGallery` (`data-testid="complaint-evidence-assets"`) |
| **Accepts / uploads** | Read-only. |
| **Current preview** | H-01 image-only lightbox. |
| **Target tier** | Tier 1 (+ 2–4 via shared component) |
| **Priority** | **P0** |

### H-05 · RTADetail — Photos tab

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/RTADetail.tsx` |
| **Component** | `EvidenceGallery` (Photos tab) |
| **Accepts / uploads** | Upload: `image/*`, `video/*`, `.pdf` (matches `SUPPORTED_EVIDENCE_MIME_*`). Delete enabled. |
| **Current preview** | H-01 image-only lightbox. |
| **Target tier** | Tier 1 (+ 2–4 via shared component) |
| **Priority** | **P0** |

### H-06 · IncidentDetail — Photos tab

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/IncidentDetail.tsx` |
| **Component** | `CaseEvidencePanel` (`sourceType="incident"`, `enableUpload`) |
| **Current preview** | H-01 via H-02. |
| **Target tier** | Inherit H-01 |
| **Priority** | **P0** |

### H-07 · ComplaintDetail — Photos tab

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/ComplaintDetail.tsx` |
| **Component** | `CaseEvidencePanel` (`sourceType="complaint"`, `enableUpload`) |
| **Current preview** | H-01 via H-02. |
| **Target tier** | Inherit H-01 |
| **Priority** | **P0** |

### H-08 · NearMissDetail — Photos tab

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/NearMissDetail.tsx` |
| **Component** | `CaseEvidencePanel` (`sourceType="near_miss"`, `enableUpload`) |
| **Current preview** | H-01 via H-02. |
| **Target tier** | Inherit H-01 |
| **Priority** | **P0** |

---

## P1 — Investigation / Action / Audit / Safety evidence

### H-09 · ComplianceScheduleDetail — occurrence evidence

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/compliance/RecordEvidenceSection.tsx` (embedded from `ComplianceScheduleDetail.tsx`) |
| **Component** | `RecordEvidenceSection` → `CaseEvidencePanel` (`sourceType="compliance_record"`) |
| **Accepts / uploads** | H-01 defaults; upload per compliance occurrence. |
| **Current preview** | H-01 via H-02 (collapsed by default). |
| **Target tier** | Inherit H-01 |
| **Priority** | **P1** |

### H-10 · InvestigationEvidence

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/investigation/InvestigationEvidence.tsx` |
| **Component** | `InvestigationEvidence` |
| **Accepts / uploads** | `image/*`, `video/*`, `application/pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`; max 50 MB; visibility selector. |
| **Current preview** | **Download-only.** Icon by `asset_type` (photo/pdf/file); `getSignedUrl` → `window.open`. No inline preview or lightbox. |
| **Target tier** | Tier 1 for image/PDF/video/audio; Tier 3 for Office |
| **Priority** | **P1** |

### H-11 · ActionDetail — Documents & evidence

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/ActionDetail.tsx` |
| **Component** | Inline attachments list (not `EvidenceGallery`) |
| **Accepts / uploads** | Images (jpeg/png/gif/webp/heic/heif), video (mp4/webm/quicktime), PDF, Word, Excel, audio (mpeg/wav/ogg); max 50 MB. |
| **Current preview** | **Download-only** list with metadata; `getSignedUrl` → new tab. No thumbnails or inline viewer. |
| **Target tier** | Tier 1–3 by MIME |
| **Priority** | **P1** |

### H-12 · AuditExecution — photo evidence grid

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/AuditExecution.tsx` |
| **Component** | `PhotoCapture` (inline) |
| **Accepts / uploads** | `image/*` capture/upload; persisted to evidence-assets on save. |
| **Current preview** | **Local data-URL `<img>` thumbnails** (3-column grid). Reload hydrates from signed URLs. No lightbox. |
| **Target tier** | Tier 1 (images); optional lightbox parity with H-01 |
| **Priority** | **P1** |

### H-13 · AuditExecution — signature preview

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/AuditExecution.tsx` |
| **Component** | `SignaturePad` (`data-testid="audit-signature-preview"`) |
| **Accepts / uploads** | Canvas PNG → evidence-assets. |
| **Current preview** | **Image preview** of captured signature (data URL / signed URL). |
| **Target tier** | Tier 1 (image) — already sufficient |
| **Priority** | **P1** |

### H-14 · MobileAuditExecution — photo evidence grid

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/MobileAuditExecution.tsx` |
| **Component** | `PhotoCapture` |
| **Accepts / uploads** | `image/*` capture. |
| **Current preview** | **Local data-URL `<img>` grid** (same pattern as H-12). |
| **Target tier** | Tier 1 |
| **Priority** | **P1** |

### H-15 · UVDBAudits — source document open

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/UVDBAudits.tsx` |
| **Component** | `handleViewPdf` |
| **Accepts / uploads** | N/A (view existing evidence asset). |
| **Current preview** | **New-tab open** via `/api/v1/evidence-assets/{id}/signed-url`. No inline iframe. |
| **Target tier** | Tier 1 (PDF expected) |
| **Priority** | **P1** |

### H-16 · CustomerAudits — evidence open

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/CustomerAudits.tsx` |
| **Component** | Evidence signed-url handler (same pattern as H-15) |
| **Accepts / uploads** | N/A |
| **Current preview** | **New-tab open** via signed URL. |
| **Target tier** | Tier 1 |
| **Priority** | **P1** |

### H-17 · SafetyAssetDetail — asset photo

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/SafetyAssetDetail.tsx` |
| **Component** | Photo evidence panel |
| **Accepts / uploads** | `image/*`; stored as `photo_evidence_id`. |
| **Current preview** | **Single `<img>`** from signed URL (`object-contain`, max-h-48). Fallback text if ID present but URL fails. |
| **Target tier** | Tier 1 — already sufficient for images |
| **Priority** | **P1** |

---

## P2 — Governance Library

### H-18 · DocumentPdfPreview (canonical Library inline viewer)

| Field | Value |
| --- | --- |
| **File** | `frontend/src/components/DocumentPdfPreview.tsx` |
| **Component** | `DocumentPdfPreview` |
| **Accepts / uploads** | N/A (reads stored Library document by `documentId`). |
| **Current preview** | **PDF:** `<iframe>` with signed URL. **Non-PDF:** message *"Inline preview is available for PDF documents"* + external open link. |
| **Target tier** | Tier 1 PDF ✓; Tier 2–3 for docx/xlsx/csv/md/txt/images |
| **Priority** | **P2** |

### H-19 · DocumentDetail — inline + header actions

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/DocumentDetail.tsx` |
| **Component** | `DocumentPdfPreview` (lazy) + `handleOpenPreview` |
| **Accepts / uploads** | Revision upload via `DocumentVersionControlBar` (`.pdf,.doc,.docx,.xlsx,.xls,.csv,.md,.txt,.png,.jpg,.jpeg`). |
| **Current preview** | Toggle **Show inline preview** → H-18. Header **Preview** / **Download** → **new tab** signed URL (any file type). |
| **Target tier** | Tier 1–3 by `file_type` |
| **Priority** | **P2** |

### H-20 · Documents — list quick open

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/Documents.tsx` |
| **Component** | Detail modal **Open** / **Download** (`handleDocumentOpen`) |
| **Accepts / uploads** | Library upload: PDF, Word, Excel, CSV, MD, TXT, PNG, JPG (max 50 MB). |
| **Current preview** | **New-tab open** or download via signed URL. Modal shows metadata/AI summary only — **no inline file render**. |
| **Target tier** | Tier 1–3; consider embedding H-18 in modal |
| **Priority** | **P2** |

---

## P3 — Portal, Planet Mark, demo / placeholder

### H-21 · PortalIncidentForm — reporter photo strip

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/PortalIncidentForm.tsx` + `frontend/src/pages/portalPhotoEvidenceHonesty.ts` |
| **Component** | `portalPhotoPreviewUrl` → local `<img>` |
| **Accepts / uploads** | `image/*` (JPG/PNG/GIF/WEBP/HEIC); max 8 photos × 10 MB. **Metadata-only** to reporter submission (binary not on evidence spine). |
| **Current preview** | **Local blob URL image grid** before submit. No post-submit preview. |
| **Target tier** | Tier 1 for intake images; persist to evidence spine (separate workstream) |
| **Priority** | **P3** |

### H-22 · PortalRTAForm — reporter photo strip

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/PortalRTAForm.tsx` |
| **Component** | `portalPhotoPreviewUrl` (shared helper) |
| **Accepts / uploads** | Same as H-21. |
| **Current preview** | Local blob `<img>` grid; metadata-only persistence. |
| **Target tier** | Tier 1 |
| **Priority** | **P3** |

### H-23 · PortalNearMissForm — reporter photo strip

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/PortalNearMissForm.tsx` |
| **Component** | `portalPhotoPreviewUrl` |
| **Accepts / uploads** | Same as H-21. |
| **Current preview** | Local blob `<img>` grid; metadata-only persistence. |
| **Target tier** | Tier 1 |
| **Priority** | **P3** |

### H-24 · PlanetMarkYearEvidencePanel — year evidence list

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/planetMarkYearEvidencePanel.tsx` |
| **Component** | Evidence list rows + `downloadEvidence` |
| **Accepts / uploads** | `.pdf,.jpg,.jpeg,.png,.webp,.xls,.xlsx,.csv` (max 20 MB). |
| **Current preview** | **Download-only** (`planetMarkApi` blob download). No inline viewer. |
| **Target tier** | Tier 1–2 by type |
| **Priority** | **P3** |

### H-25 · ReportChat — attachment chips

| Field | Value |
| --- | --- |
| **File** | `frontend/src/components/ReportChat.tsx` |
| **Component** | `AttachmentPreview` |
| **Accepts / uploads** | Demo/mock attachments (`image`, `video`, `document`). |
| **Current preview** | **Image:** 40×40 thumbnail. **Other:** icon + download link. Not wired to production evidence API. |
| **Target tier** | Tier 1 when wired to real storage |
| **Priority** | **P3** |

### H-26 · DigitalSignatures — sign dialog placeholder

| Field | Value |
| --- | --- |
| **File** | `frontend/src/pages/DigitalSignatures.tsx` |
| **Component** | Sign modal "Document Preview" block |
| **Accepts / uploads** | N/A |
| **Current preview** | **Placeholder text** (title + description); not a real document render. |
| **Target tier** | Tier 1 (PDF) when wired to document store |
| **Priority** | **P3** |

### H-27 · DynamicFormRenderer — file / image fields

| Field | Value |
| --- | --- |
| **File** | `frontend/src/components/DynamicForm/DynamicFormRenderer.tsx` |
| **Component** | `file` / `image` field types |
| **Accepts / uploads** | Image: `image/*`. File: `image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf`. |
| **Current preview** | **Filename chips only** after selection; no thumbnail or inline viewer. |
| **Target tier** | Tier 1–3 by selected file type |
| **Priority** | **P3** |

### H-28 · Planet Mark legacy upload row

| Field | Value |
| --- | --- |
| **File** | `frontend/src/components/planet-mark/EvidenceUploadRow.tsx` |
| **Component** | `EvidenceUploadRow` |
| **Accepts / uploads** | `.pdf,.jpg,.jpeg,.png,.webp,.xls,.xlsx,.csv` (max 20 MB). |
| **Current preview** | **Upload status only** (success/duplicate filename); no post-upload preview. |
| **Target tier** | Tier 1–2 when list/preview added |
| **Priority** | **P3** |

---

## EvidenceGallery current gap summary (P0)

`EvidenceGallery` is the highest-impact preview host: **8 embed points** (H-01–H-08)
cover incidents, complaints, RTAs, near-misses, and compliance occurrences.

| Capability | Upload accepted | Preview today | Gap |
| --- | --- | --- | --- |
| **Images** | ✓ `image/*` | ✓ Thumbnail + dialog lightbox (signed URL) | Failed signed URL shows "Preview unavailable"; no retry |
| **Video** | ✓ `video/*` | ✗ Icon + MIME label; dialog: *cannot be previewed* | Needs Tier 1 `<video>` player |
| **PDF** | ✓ `application/pdf` | ✗ Icon + MIME label; dialog: *cannot be previewed* | Needs Tier 1 iframe (reuse `DocumentPdfPreview` pattern) |
| **Audio** | ✗ not in default accept | ✗ | Not accepted; ActionDetail accepts audio but not via gallery |
| **Office** | ✗ | ✗ | InvestigationEvidence accepts; gallery does not |
| **CSV / text** | ✗ | ✗ | Not in evidence upload path |
| **Lightbox UX** | — | Dialog with prev/next + keyboard arrows | PDF/video would need in-dialog renderer, not download-only message |
| **Non-image download** | ✓ | Download button in dialog | Works; preview message is honest today |

**Recommended uplift order:** (1) PDF in dialog via shared Tier-1 renderer, (2) video
`<video controls>`, (3) align upload accept lists across ActionDetail /
InvestigationEvidence / EvidenceGallery, (4) Office + CSV via Tier 2–3 viewers.

---

## Out of scope (upload-only, no preview host)

These accept files but do not render stored content:

- `frontend/src/pages/PortalFireDrill.tsx` — photo input, no preview strip
- `frontend/src/pages/Documents.tsx` — upload modal (pre-ingest)
- `frontend/src/components/DocumentVersionControlBar.tsx` — revision file picker
- `frontend/src/pages/planetMarkYearOcrPanel.tsx` — OCR **text-field** preview, not document render
- `frontend/src/pages/DocumentCampaignResults.tsx` — evidence **pack export** download only

---

## Search index (code anchors)

| Term | Primary locations |
| --- | --- |
| `EvidenceGallery` | `frontend/src/components/EvidenceGallery.tsx`, case detail Photos tabs |
| `cannot be previewed` | `EvidenceGallery.tsx:367` |
| `lightbox` | `EvidenceGallery` Dialog (no `lightbox` class name; dialog acts as lightbox) |
| `DocumentViewer` | *Not present* — Library uses `DocumentPdfPreview` |
| `DocumentPdfPreview` | `frontend/src/components/DocumentPdfPreview.tsx`, `DocumentDetail.tsx` |
| `mime` / accept | Per-host tables above; defaults in `DEFAULT_EVIDENCE_*` constants |
| `Attachment` / `FilePreview` | `ReportChat.tsx` (`AttachmentPreview`); no `FilePreview` component |
| `Library viewer` | `DocumentDetail` inline toggle + `Documents` modal metadata |
