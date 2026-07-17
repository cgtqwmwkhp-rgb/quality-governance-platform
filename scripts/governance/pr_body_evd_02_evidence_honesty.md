# Change Ledger (CL-EVD-02-EVIDENCE-HONESTY)

**Path claim:** `path11/evd-02-evidence-honesty`

## File allowlist (exclusive)

- `frontend/src/pages/PortalIncidentForm.tsx`
- `frontend/src/pages/portalPhotoEvidenceHonesty.ts`
- `frontend/src/pages/__tests__/portalPhotoEvidenceHonesty.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_evd_02_evidence_honesty.md`

**Zero overlap** with parallel lanes: CMP-08 (`ComplaintDetail*`), CA-W1b, AUD-PHOTO-03, Documents* (LIB-04), Layout/App/client.ts, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 EVD-02 — Portal photo upload honesty toward evidence-assets spine
- **User goal:** Portal reporters understand that selected photos record filenames/sizes only today — binaries are not yet uploaded to the shared evidence store from the public portal.
- **In scope:** FE honesty copy + metadata `evidence_spine: metadata_only` flag; helpers + vitest; en/cy
- **Out of scope:** Backend portal multipart upload (follow-on); Documents list; Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Portal incident/complaint photos UI | Silent metadata attach | Honesty banner under Photos |
| `reporter_submission.photos` | `{count,files}` | Adds `evidence_spine: 'metadata_only'` |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive metadata field; tolerant readers ignore unknown keys
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Portal photos section shows evidence-spine honesty copy
- [x] AC-02: Submitted photo summary includes `evidence_spine: metadata_only`
- [x] AC-03: Helper unit tests cover copy + detection
- [x] AC-04: cy/en keys present for new honesty string (≥95% cy for new keys)
- [x] AC-05: No Alembic / Documents* / client.ts changes

## 5) Testing Evidence

- [x] Vitest — `portalPhotoEvidenceHonesty.test.ts` (3 passed)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Portal incident form Photos step — honesty banner visible with/without files
- [x] CUJ-02: Submit path stamps metadata-only spine flag (no binary upload claimed)

## 7) Observability & Ops

- **Playwright hooks:** `portal-photo-evidence-honesty`
- **Follow-on:** Authenticated portal → evidence-assets upload after staff record id exists

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke portal incident photos step

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Follow-on BE: portal multipart → evidence-assets when public upload contract lands

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (PortalIncidentForm* + soft en/cy)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/portalPhotoEvidenceHonesty.test.ts`
- [ ] Manual: portal incident Photos step shows honesty copy
