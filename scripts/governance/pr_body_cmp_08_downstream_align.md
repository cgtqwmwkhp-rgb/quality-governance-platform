# Change Ledger (CL-CMP-08-DOWNSTREAM-ALIGN)

**Path claim:** `path11/cmp-08-downstream-align`

## File allowlist (exclusive)

- `frontend/src/pages/ComplaintDetail.tsx`
- `frontend/src/pages/complaintEvidenceHonesty.ts`
- `frontend/src/pages/__tests__/ComplaintDetail.test.tsx`
- `frontend/src/pages/__tests__/complaintEvidenceHonesty.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_cmp_08_downstream_align.md`

**Zero overlap** with parallel lanes: EVD-02 (`PortalIncidentForm*`), CA-W1b, AUD-PHOTO-03, Documents*, Layout/App/client.ts, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 CMP-08 — Complaint detail evidence + downstream inv/actions honesty
- **User goal:** Staff see real evidence-assets on complaint detail (not only portal filename metadata) and honest downstream investigation/actions guidance.
- **In scope:** List `source_module=complaint` assets; rail/summary honesty; inv/actions honesty copy; helpers + vitest; en/cy
- **Out of scope:** Portal upload binary wiring (EVD-02 / BE follow-on); Complaints board redesign
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Evidence rail | Reporter “N uploaded” metadata only | Prefers evidence-asset count; honest when metadata-only |
| Overview | No assets list | Evidence assets card (parity with IncidentDetail) |
| Investigation / actions | Counts only | Downstream honesty copy |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Read-only evidence-assets list; same API as CMP-07 create uploads
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Complaint detail lists evidence-assets for `source_module=complaint`
- [x] AC-02: Empty assets state distinguishes portal filename metadata vs spine
- [x] AC-03: Downstream investigation honesty renders
- [x] AC-04: Downstream open-actions honesty renders
- [x] AC-05: Vitest covers helpers + ComplaintDetail CMP-08 case

## 5) Testing Evidence

- [x] Vitest — `complaintEvidenceHonesty.test.ts`, `ComplaintDetail.test.tsx` (12 passed)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Complaint with staff-uploaded asset — asset title surfaces on detail
- [x] CUJ-02: Complaint with portal metadata only — empty assets + honest reporter summary

## 7) Observability & Ops

- **Playwright hooks:** `complaint-evidence-assets`, `complaint-evidence-assets-empty`, `complaint-evidence-summary`, `complaint-downstream-inv-honesty`, `complaint-downstream-actions-honesty`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke complaint detail with/without evidence assets

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: CMP-07 create upload (#1044), IncidentDetail evidence surfacing

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (ComplaintDetail* + soft en/cy; no Portal*)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/complaintEvidenceHonesty.test.ts src/pages/__tests__/ComplaintDetail.test.tsx`
- [ ] Manual: complaint with create-upload attachment shows in Evidence assets card
