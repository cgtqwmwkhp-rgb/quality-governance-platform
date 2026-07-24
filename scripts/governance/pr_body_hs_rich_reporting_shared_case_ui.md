# Change Ledger (CL-HS-RICH-SHARED-CASE-UI)

## 1) Summary

- **Feature / Change name:** HS-RICH-SHARED-CASE-UI (Lane D) — shared case evidence + structured witnesses components
- **User goal (1–2 lines):** Extract and generalize the RTA evidence-upload and structured-witnesses UX into reusable, source-agnostic components so any case type (incident / near-miss / complaint / RTA) can adopt the same best-in-class evidence and witness capture experience.
- **In scope:** `EvidenceGallery` opt-in upload + permission-gated delete; new `CaseEvidencePanel` (fetch/upload/delete wrapper keyed by `sourceType` + `sourceId`); new `CaseWitnessesPanel` (controlled structured witnesses editor matching the RTA `witnesses_structured` shape); component tests; new `case.evidence.*` / `case.witnesses.*` en/cy translation keys; this Change Ledger.
- **Out of scope:** Wiring these components into `IncidentDetail`, `NearMissDetail`, `ComplaintDetail`, or `RTADetail` (Lane E); any backend/API changes; `employee_portal.py`.
- **Feature flag / kill switch:** N/A — new components are unused until a page imports them; `EvidenceGallery`'s new props are opt-in and default to the prior read-only behaviour, so no existing call site changes behaviour.

## 2) Impact Map (what changed)

- **Frontend (routes/screens/components):**
  - `EvidenceGallery.tsx` — added `enableUpload`, `uploadSourceModule`, `uploadSourceId`, `onUploadComplete`, `uploadLabel`, `uploadAccept`, `maxFileSizeBytes`, `allowedMimePrefixes`, `allowedMimeTypes`, and `canDelete`. All default to the previous read-only, delete-only-when-`onDelete`-supplied behaviour — zero change for existing callers (`RTADetail`, `InvestigationEvidence`, etc.).
  - `components/case/CaseEvidencePanel.tsx` (new) — thin wrapper owning `evidenceAssetsApi` fetch/upload/delete for `sourceType: 'incident' | 'near_miss' | 'complaint' | 'road_traffic_collision'` + `sourceId`.
  - `components/case/CaseWitnessesPanel.tsx` (new) — fully controlled (`value`/`onChange`/`readOnly`) structured witnesses editor (name, phone, email, statement, optional "willing to provide a statement" consent), with an accessible read-only summary mode.
  - No page wiring — pages are untouched per the exclusive allowlist.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None — reuses existing `evidenceAssetsApi.list/upload/delete/getSignedUrl`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None — `CaseWitnessesPanel`'s `CaseWitnessesValue` (`{ witnesses?: Witness[] }`) mirrors the existing `RTA.witnesses_structured` field exactly so it can be dropped in without a payload shape change.
- **Database (migrations/entities/indexes):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Purely additive. `EvidenceGallery` upload UI only renders when `enableUpload` is true **and** both `uploadSourceModule` + `uploadSourceId` are supplied; otherwise it stays exactly as before (no toolbar, same grid/empty-state markup). Delete keeps working exactly as before when only `onDelete` is passed.
- **Tolerant reader / strict writer applied?** Yes — `CaseEvidencePanel` treats load failures as an explicit "could not load" state (never a fabricated empty list); per-file upload failures are collected and shown inline without blocking successfully uploaded files in the same batch.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** N/A — revert PR only.

## 4) Acceptance Criteria (AC)

- [x] AC-01: `EvidenceGallery` supports opt-in upload (file picker → `evidenceAssetsApi.upload({ source_module, source_id, ... })` → caller-driven refresh via `onUploadComplete`) while remaining fully read-only by default.
- [x] AC-02: `EvidenceGallery` delete affordance is gated by both `onDelete` presence and the new `canDelete` permission prop.
- [x] AC-03: `CaseEvidencePanel` exposes a clean `{ sourceType, sourceId, title, enableUpload }` API and owns its own list/upload/delete lifecycle.
- [x] AC-04: `CaseWitnessesPanel` edits/reads the exact `{ witnesses: Witness[] }` shape used by RTA's `witnesses_structured`, with accessible labelled inputs, add/remove, and a distinct read-only summary view.
- [x] AC-05: Vitest coverage for happy path and empty state on both new panels, plus an `EvidenceGallery` upload-specific test file.
- [x] AC-06: No emoji decoration; empty states, disabled states, and error messages are explicit and honest (e.g. unsupported file type / size-limit messages, load-failed vs. empty distinguished).
- [x] AC-07: Exclusive allowlist respected — no edits to `IncidentDetail.tsx`, `NearMissDetail.tsx`, `ComplaintDetail.tsx`, `RTADetail.tsx`, `employee_portal.py`, or any backend file.

## 5) Testing Evidence (link to runs)

- [x] Lint — `npx eslint src/components/EvidenceGallery.tsx src/components/case/CaseWitnessesPanel.tsx src/components/case/CaseEvidencePanel.tsx src/components/case/__tests__/*.test.tsx src/components/__tests__/EvidenceGallery.upload.test.tsx --max-warnings 0` (local, clean)
- [x] Typecheck — `npx tsc --noEmit` (local, clean)
- [x] Unit tests — `npx vitest run src/components/case/__tests__/CaseWitnessesPanel.test.tsx src/components/case/__tests__/CaseEvidencePanel.test.tsx src/components/__tests__/EvidenceGallery.upload.test.tsx src/components/EvidenceGallery.test.tsx` (local, 15/15 passing)
- [x] Regression sweep — `npx vitest run src/components/case src/components` (local, 49 files / 234 tests passing)
- [ ] i18n gate — not run standalone; new `case.evidence.*` / `case.witnesses.*` keys added to both `en.json` and `cy.json` with matching key sets.
- [x] Integration/Contract/E2E — N/A (new components are not yet wired into any page; Lane E covers page integration).

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: With `enableUpload` off (default), `EvidenceGallery` renders identically to before — no upload affordance appears even if a source is supplied.
- [x] CUJ-02: With `enableUpload` on and a valid source, selecting files uploads each via `evidenceAssetsApi.upload`, surfaces per-file validation errors (unsupported type / over size limit) without discarding valid files, and calls `onUploadComplete` for the caller to refetch.
- [x] CUJ-03: `CaseEvidencePanel` loads by `sourceType`/`sourceId`, shows an honest empty state, and deletes + refreshes on confirmation.
- [x] CUJ-04: `CaseWitnessesPanel` adds/edits/removes witnesses in edit mode and renders a read-only, control-free summary (including the write-a-statement consent) in read-only mode.

## 7) Observability & Ops

- **Logs:** No change.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local → Staging → Canary → Prod)

- **Staging verification:** N/A until Lane E wires a page to these components (this lane ships components only).
- **Canary plan:** N/A.
- **Prod post-deploy checks:** N/A for this lane; verify on the consuming page's rollout instead.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** Regression in `EvidenceGallery` read-only rendering for existing call sites (RTA photos tab, investigation evidence, etc.).
- **Rollback steps:** Revert PR — new props are additive/opt-in so no other page is affected until wired up.
- **Owner:** Frontend / Case UI track.

## 10) Evidence Pack (links)

- CI run(s): linked after PR creation.
- Staging deploy evidence: N/A — components only, not yet wired into a page.
- Canary evidence: N/A.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** No backend/API surface added; reuses existing `evidenceAssetsApi` and `Witness` types.
- [ ] **Gate 2:** CI green (lint/type/build/tests) — pending remote CI run.
- [ ] **Gate 3:** Staging verification — N/A until Lane E wires a page; revisit when that PR lands.
- [x] **Gate 4:** Rollback plan verified.
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted.

## Exclusive allowlist (this PR)

- `frontend/src/components/EvidenceGallery.tsx`
- `frontend/src/components/case/CaseWitnessesPanel.tsx` (new)
- `frontend/src/components/case/CaseEvidencePanel.tsx` (new)
- `frontend/src/components/case/__tests__/CaseWitnessesPanel.test.tsx` (new)
- `frontend/src/components/case/__tests__/CaseEvidencePanel.test.tsx` (new)
- `frontend/src/components/__tests__/EvidenceGallery.upload.test.tsx` (new)
- `frontend/src/i18n/locales/en.json` (new `case.evidence.*` / `case.witnesses.*` keys only)
- `frontend/src/i18n/locales/cy.json` (new `case.evidence.*` / `case.witnesses.*` keys only)
- `scripts/governance/pr_body_hs_rich_reporting_shared_case_ui.md`

**Zero overlap with `IncidentDetail.tsx`, `NearMissDetail.tsx`, `ComplaintDetail.tsx`, `RTADetail.tsx`, `employee_portal.py`, or any backend file.** Page-level wiring is explicitly deferred to Lane E.
