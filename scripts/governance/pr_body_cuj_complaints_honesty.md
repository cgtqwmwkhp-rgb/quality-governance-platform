# Change Ledger (CL-CUJ-COMPLAINTS-HONESTY)

## File allowlist (exclusive)

- `frontend/src/pages/Complaints.tsx`
- `frontend/src/pages/ComplaintDetail.tsx`
- `frontend/src/pages/__tests__/Complaints.test.tsx`
- `frontend/src/pages/__tests__/Complaints.a11y.test.tsx`
- `frontend/src/pages/__tests__/ComplaintDetail.test.tsx`
- `frontend/tests/e2e/complaint-lifecycle-cuj.spec.ts`
- `scripts/smoke/complaint_lifecycle_e2e.py`
- `tests/e2e/uat/test_complaint_lifecycle.py`
- `docs/uat/UAT_TEST_SCRIPT.md` (Complaints CUJ checklist only)
- `scripts/governance/pr_body_cuj_complaints_honesty.md`

**Zero overlap** with parallel owners: `Layout.tsx` admin hub, compliance audit-pack, SWA workflow, `AnimatedOutlet`, `Actions.tsx` My Work. Prefer English literals / `t(..., default)` (no `en.json`/`cy.json`). Parked SMTP secrets — never invent delivery.

## 1) Summary

- **Feature / Change name:** CUJ — Complaints honesty + proof (≥8.5)
- **User goal:** Operators never confuse list outage with an empty register; see SMTP honesty when outbound email is down; prove create → list → detail end-to-end.
- **In scope:** List unavailable vs empty; Live/Unavailable badges; SMTP banners on list + detail/action; null-safe search; create navigates to detail; vitest + Playwright CUJ-03/04; smoke list+get; UAT journey + checklist
- **Out of scope:** Layout/admin hub; Actions My Work; audit-pack; SWA; inventing SMTP/secrets; locale file edits
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Complaints list failure | Error banner + “No complaints found” empty theatre | Unavailable empty state + toast; never fake empty |
| SMTP down | No operator signal on Complaints | Amber honesty banners (list + detail + action modal) |
| Create complaint | Stay on list silently | Toast + navigate to `/complaints/:id` |
| Client search | Could throw on null complainant | Null-safe filter |
| Proof | Detail lifecycle only | CUJ-03 create→list→detail + CUJ-04 SMTP/unavailable; smoke list+get; UAT checklist |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UX/proof only — consumes existing `/readyz` `email_configured`
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: List API failure shows **Complaints unavailable** (not “No complaints found”)
- [x] AC-02: Banner when `email_configured=false` on list and detail; action create toast is honest
- [x] AC-03: Create → navigate to detail; Playwright CUJ-03 + smoke list+get prove journey
- [x] AC-04: Client search does not crash on null complainant fields

## 5) Testing Evidence

- [x] Vitest `Complaints.test.tsx` — unavailable, SMTP banner, create→detail, null-safe search
- [x] Vitest `ComplaintDetail.test.tsx` — SMTP banner + action-modal honesty toast
- [x] Playwright `complaint-lifecycle-cuj.spec.ts` — CUJ-01..04
- [x] Smoke `complaint_lifecycle_e2e.py` — `list_complaints` + `get_complaint_detail`
- [x] UAT `test_complaint_lifecycle.py` — create→list→get path contract
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Investigation modal API-honest; stay on detail
- [x] CUJ-02: Key dates + running sheet
- [x] CUJ-03: Create → list → detail
- [x] CUJ-04: SMTP honesty + unavailable ≠ empty

## 7) Observability & Ops

- Operator-visible toast on list failure and create success
- `data-testid`: `complaints-email-unavailable`, `complaints-list-unavailable`, `complaints-live-badge`, `complaint-detail-email-unavailable`, `complaint-action-email-unavailable`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human)
3. Staging tip + `/healthz`
4. Force-deploy prod with full SHA when approved

## 9) Rollback Plan

1. Revert squash commit
2. Redeploy previous known-good SHA
3. Verify `/api/v1/meta/version`

## Gate checklist

- [x] Gate 0 — change ledger
- [x] Gate 1 — allowlist only (no Layout/Actions/SWA/audit-pack)
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack attached
