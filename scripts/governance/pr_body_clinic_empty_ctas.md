# Change Ledger (CL-CLINIC-EMPTY-CTAS)

## File allowlist (exclusive)
- `frontend/src/pages/DocumentControl.tsx`
- `frontend/src/pages/KnowledgeExceptions.tsx`
- `frontend/src/pages/Standards.tsx`
- `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `scripts/governance/pr_body_clinic_empty_ctas.md`

## 1) Summary
- **Feature / Change name:** Clinic depth — empty-state CTAs
- **User goal:** Empty Document Control, Exceptions, and Standards surfaces offer a clear next action instead of a dead end.
- **In scope:** EmptyState actions only (New draft / Clear filters / Open standards or compliance)
- **Out of scope:** Full Doc Control publish CUJ; Exceptions confirm/reject workflow; Standards seeding backend
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map
- **Frontend:** DocumentControl, KnowledgeExceptions, Standards empty states
- **Backend:** None

## 3) Compatibility & Data Safety
- Additive UI CTAs; no API/schema changes
- Rollback: revert commit

## 4) Acceptance Criteria
- [x] Document Control empty list → New draft opens create
- [x] Exceptions filtered empty → Clear filters; inbox clear → Open standards map
- [x] Standards empty catalog → Open ISO Compliance; search miss → Clear filters
- [x] Vitest covers Exceptions empty CTAs

## 5) Testing Evidence
- [x] `npx vitest run src/pages/__tests__/KnowledgeExceptions.test.tsx`
- [ ] CI green — this PR

## 6) Release / Rollback
1. Squash-merge when CI green
2. Rollback: revert squash on main
