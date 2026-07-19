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
- **Compatibility strategy:** FE-only
- **Breaking changes:** None
- Rollback: revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Document Control empty list → New draft opens create
- [x] AC-02: Exceptions filtered empty → Clear filters; inbox clear → Open standards map
- [x] AC-03: Standards empty catalog → Open ISO Compliance; search miss → Clear filters

## 5) Testing Evidence
- [x] Vitest — KnowledgeExceptions empty CTA tests
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Empty Document Control → New draft CTA opens create shell
- [x] CUJ-02: Empty Exceptions inbox → Open standards map deep-link

## 7) Observability & Ops
- Playwright hooks: `document-control-empty-new-draft` (where present); no new metrics

## 8) Release Plan
1. Squash-merge when CI green
2. Tip smoke `/document-control`, `/knowledge-exceptions`, `/standards` empty states

## 9) Rollback Plan
1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready
