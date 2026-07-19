# Change Ledger (CL-GOV-LIB-W4B-DASHBOARDS)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W4b — Library / HSEQ dashboard and PEL dependency map
- **User goal:** Give Library and Admin users honest, tenant-scoped counts for statutory documents, overdue reviews, and open review packs; expose a PEL reference's current tip and immutable superseded history.
- **Depends on:** W3 LIVE; W4a (#1181) must be LIVE before this branch is rebased and opened.
- **In scope:** Additive dashboard-summary and dependency-map APIs, thin Admin Dashboard HSEQ tiles, unit/contract coverage, and Change Ledger.
- **Out of scope:** W4a offer/campaign approval flow and Document Detail CTAs, migrations, new campaign or review-pack stacks, and any automatic dependency writes.

## 2) Impact Map
- **Frontend:** Admin Dashboard adds three thin Library / HSEQ tiles using existing design tokens.
- **Backend:** `library_review_service.py` composes existing horizons, `documents.is_statutory`, and review-pack models.
- **APIs:** `GET /api/v1/library-review/dashboard-summary`; `GET /api/v1/library-review/dependencies/{pel_doc_ref}`.
- **Schemas/contracts:** Additive `library_review` response schemas and typed frontend client.
- **Database:** No migration or schema change.
- **Dependencies:** Reuses W3 review packs/horizons and existing `DocumentVersion` supersession history.

## 3) Compatibility & Data Safety
- Additive only; no existing API or UI contract is changed.
- Every query is tenant-scoped.
- The dependency map is read-only and returns the document's actual current tip plus only immutable `superseded` version rows.
- W4a endpoints and campaign workflow are deliberately untouched.

## 4) Acceptance Criteria
- [x] AC-01: Admin shows statutory-document, overdue-review, and open-review-pack HSEQ tiles.
- [x] AC-02: Dashboard summary composes existing horizon overdue count, `is_statutory`, and open review packs.
- [x] AC-03: Dashboard summary has no cross-tenant reads.
- [x] AC-04: PEL dependency endpoint returns a current document tip and superseded version history.
- [x] AC-05: Unknown PEL references return the existing not-found contract.
- [x] AC-06: No new migration, type ignore, review-pack stack, or campaign stack is introduced.
- [x] AC-07: Existing Portal / My Reading campaign-reading coverage remains in place.
- [x] AC-08: Unit tests cover summary composition and dependency history filtering.

## 5) Testing Evidence
- [x] Unit: `python3.11 -m pytest tests/unit/test_gov_lib_w4b_dashboard_deps.py tests/unit/test_gov_lib_w3_review_packs.py -q` — 23 passed locally.
- [ ] Frontend: `npm test -- AdminDashboard.test.tsx` — run in CI/local frontend environment.
- [ ] CI: linked by future W4b PR.
- [ ] Staging: after W4a rebase and PR merge.

## 6) Critical Journeys Verified
- [x] CUJ-01: HSEQ/admin dashboard summary includes overdue review count from the W3 horizon service.
- [x] CUJ-02: A statutory document and open review packs contribute independently to their tiles.
- [x] CUJ-03: PEL reference returns current tip plus only `superseded` history.
- [x] CUJ-04: Existing Portal Reading coverage confirms campaign assignment open/read path is retained.

## 7) Observability & Ops
- **Logs:** Existing API request/error logging; no new sensitive values or background tasks.
- **Metrics:** Dashboard API latency/error rate via existing API observability.
- **Alerts:** Existing API 5xx alerting applies; no new alert threshold.
- **Evidence Pack:** Unit run above; future CI link; staging screenshot/API responses after W4a rebase.

## 8) Release and Rollback
- **Release:** Rebase this main-based branch after W4a (#1181) is LIVE, run unit + frontend tests, then open PR.
- **Staging checks:** Verify summary counts against tenant documents/packs and fetch a known `pel_doc_ref` history.
- **Rollback:** Revert this additive commit; no data rollback or migration is required.

---

# Gate Checklist
- [x] **Gate 0:** Scope locked; W4a explicitly excluded; Change Ledger complete.
- [x] **Gate 1:** Additive API/data/UX contracts defined; tenant scoping and read-only history enforced.
- [ ] **Gate 2:** CI green (Python unit + frontend test/build).
- [ ] **Gate 3:** Staging verification completed after W4a rebase.
- [x] **Gate 4:** Canary N/A — read-only additive dashboard data.
- [x] **Gate 5:** Production verification and observability evidence defined.
