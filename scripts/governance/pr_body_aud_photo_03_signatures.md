# Change Ledger (CL-AUD-PHOTO-03-SIGNATURES)

**Path claim:** `path11/aud-photo-03-signatures`

## File allowlist (exclusive)

- `frontend/src/pages/AuditExecution.tsx`
- `frontend/src/pages/auditExecutionPhotoEvidence.ts`
- `frontend/src/pages/__tests__/auditExecutionPhotoEvidence.test.ts`
- `scripts/governance/pr_body_aud_photo_03_signatures.md`

**Zero overlap** with parallel lanes: CA-W1b (`ComplianceAutomation*`), EVD-02 (`Portal*`), CMP-08 (`ComplaintDetail*`), Audits board redesign, `IMSDashboard*`, Layout/App/client.ts, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 AUD-PHOTO-03 — Signature pad persist honesty via evidence-assets
- **User goal:** Audit signature answers persist on the shared evidence spine like photos — not session-only canvas data URLs that vanish on reload.
- **In scope:** SignaturePad upload/hydrate/clear; helpers; unit tests
- **Out of scope:** MobileAuditExecution rewrite; Audits board; backend schema changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Signature capture | Local data URL only | Upload PNG to evidence-assets; `response_json.evidence_asset_ids` |
| Reopen run | Blank canvas / lost signature | Hydrates signed URL into signature preview |
| Clear signature | Cleared local state | Clears local state + best-effort asset delete |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Same evidence-assets spine as AUD-PHOTO-01 photos
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge (prior signatures without assets remain response_value=`signed`)

## 4) Acceptance Criteria (AC)

- [x] AC-01: Signature capture uploads to `source_module=audit` evidence-assets
- [x] AC-02: Asset id stored on answer `response_json.evidence_asset_ids`
- [x] AC-03: Rehydrate shows signature preview from signed URL
- [x] AC-04: Clear removes local signature and attempts asset delete
- [x] AC-05: Helper unit tests cover signature filename / data-URL detection

## 5) Testing Evidence

- [x] Vitest — `auditExecutionPhotoEvidence.test.ts` (4 passed)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Auditor signs a signature question — upload ACK + persisted honesty copy
- [x] CUJ-02: Reopen in-progress run — signature preview restores from evidence spine

## 7) Observability & Ops

- **Playwright hooks:** `audit-signature-pad`, `audit-signature-preview`, `audit-signature-persisted`, `audit-signature-uploading`, `audit-signature-clear`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: execute audit with signature question; reload; confirm preview

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: AUD-PHOTO-01/02 photo spine pattern

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (AuditExecution FE only)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/auditExecutionPhotoEvidence.test.ts`
- [ ] Manual: signature question → save → reload → preview present
