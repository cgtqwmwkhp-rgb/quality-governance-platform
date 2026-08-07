# Change Ledger (CL-EVIDENCE-INLINE-PREVIEW)

## 1) Summary
- **Feature / Change name:** Evidence signed-URL inline disposition for PDF/media previews
- **User goal (1–2 lines):** Occurrence evidence PDF (and other in-app-previewable media) opens in the modal instead of forcing a browser download.
- **In scope:** Backend `GET …/evidence-assets/{id}/signed-url` disposition coercion; pure helper + unit tests; OpenAPI/query docs; this Change Ledger.
- **Out of scope:** Frontend changes (already requests `disposition=inline`); Doc Graph; Azure appsettings PUT; broadening inline to Office/HTML/octet-stream.
- **Feature flag / kill switch:** None — behaviour fix on existing authenticated, tenant-scoped signed URLs.

## 2) Impact Map (what changed)
- **Frontend:** None (already asks for inline when `canPreviewInApp`).
- **Backend:** `src/api/utils/evidence_disposition.py` (new helper); `src/api/routes/evidence_assets.py` uses helper for effective disposition.
- **APIs:** Same endpoint; `disposition=inline` now honoured for `image/*`, `application/pdf`, `video/*`, `audio/*` (was images-only). Default remains `attachment`.
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** `tests/unit/test_evidence_signed_url_disposition.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive widening of an existing server-side allowlist; callers that omit disposition or pass `attachment` are unchanged.
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit / redeploy prior image.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| PDF modal preview | FE requests inline; BE coerces PDF → attachment → blank iframe + download | PDF + image/video/audio may be inline when requested |
| Non-previewable types (Office, octet-stream, HTML) | attachment | Still attachment even if client asks inline |
| Empty/unknown content_type + inline | attachment | attachment |
| Signed URL TTL / auth / tenant scope | Time-limited, auth + tenant filters | Unchanged |
| Arbitrary HTML/octet-stream inline XSS surface | Not allowed | Still not allowed |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `resolve_evidence_signed_url_disposition("inline", "image/jpeg")` → `inline`
- [x] **AC-02:** `…("inline", "application/pdf")` → `inline`; `…("attachment", "application/pdf")` → `attachment`
- [x] **AC-03:** `…("inline", "video/mp4"|"audio/mpeg")` → `inline`
- [x] **AC-04:** Office / empty / None / octet-stream / HTML + inline → `attachment`
- [x] **AC-05:** Route query description and docstring no longer say “images only”
- [x] **AC-06:** Auth, tenant scoping, and URL expiry behaviour unchanged

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_evidence_signed_url_disposition.py` (parametrized cases above)
- [ ] Lint / typecheck / build — CI
- [ ] Integration / E2E — CI; LIVE smoke: open occurrence evidence PDF in modal (no forced download)

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Operator opens occurrence evidence PDF → modal shows inline PDF preview (signed URL with inline disposition).
- [x] **CUJ-02:** Operator downloads / opens non-previewable Office evidence → still attachment download.
- [x] **CUJ-03:** Image evidence preview continues to work with `disposition=inline`.

## 7) Observability & Ops
- **Logs:** No new signals.
- **Runbook:** If modal is blank, confirm asset `content_type` is preview-safe and signed URL not expired; download path remains available.

## 8) Release Plan
- Squash-merge to `main` → Main CI → Azure deploy → verify ACA image / `build_sha` = tip SHA; prod `/healthz` + `/readyz` 200.

## 9) Rollback Plan
- **Owner:** on-call maintainer / PR author at merge time
- **Rollback steps:** Revert squash commit on `main` and allow governed redeploy of prior image. No DB rollback.
- **Rollback trigger:** Evidence previews regress, unexpected Content-Disposition for non-media types, or storage/auth failures on signed URLs.

## 10) Evidence Pack
- CI / staging / prod tip: linked after PR merges and deploy verifies LIVE

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** API/Data/UX contracts (inline allowlist aligned to FE tier-1 preview types)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
