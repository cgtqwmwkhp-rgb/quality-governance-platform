# Change Ledger (CL-GOV-LIB-W1-FILING-LIFECYCLE)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W1 — filing + lifecycle alignment
- **User goal (1–2 lines):** Enforce governance filing rules on library upload/create, align submit/approve/reject lifecycle with DocumentStatus vocabulary, supersede prior approved rows sharing a PEL ref on approve, and harden signed-url access with ACL re-check + download audit — building on Wave W0 taxonomy/PEL foundation.
- **Depends on:** [#1176](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1176) (`feat/gov-lib-w0-taxonomy-pel`) — this PR is stacked on that branch until W0 merges; rebase onto `main` when W0 lands.
- **In scope:** Filing validation (level-2 active category, access_level default from category, statutory default for 03.x/04.x, duplicate warn); lifecycle endpoints `submit` / `approve` / `reject`; PEL-ref supersession + `retention_until` on approve; signed-url ACL (404-not-403) + `library_document_access_logs`; preserve governance lifecycle status during indexing for filed docs
- **Out of scope:** Full RBAC facet wrapper (W2), review packs / AI horizon (W3), disposal queue (W5), Sites admin UI
- **Feature flag / kill switch:** None — additive columns/endpoints; legacy upload without `category_id` unchanged

## 2) Impact Map (what changed)
- **Backend services:**
  - `src/domain/services/document_library_filing_service.py` — filing rules, duplicate detection, retention parse, ACL, PEL supersession helper
  - `src/domain/services/document_library_lifecycle_service.py` — submit / approve / reject transitions
  - `src/domain/services/index_job_service.py` — preserve DRAFT/UNDER_REVIEW/etc. for filed documents during indexing
- **API routes (`src/api/routes/documents.py`):**
  - Upload applies filing defaults + duplicate warning when `category_id` set; governance uploads start as `draft`
  - `POST /documents/{id}/submit` — draft → under_review
  - `POST /documents/{id}/approve` — under_review → approved (no self-approve)
  - `POST /documents/{id}/reject` — under_review → draft
  - `GET /documents/{id}` + `GET .../signed-url` — ACL re-check (404-not-403) + access log
- **Database:** `20260719_gov_lib_w1_filing` — `documents.access_level`, `is_statutory`, `retention_until`, `duplicate_warning`, `duplicate_warning_detail`; `library_document_access_logs`
- **Tests:** `tests/unit/test_gov_lib_w1_filing_lifecycle.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive nullable/defaulted columns; new optional response fields; legacy non-filed uploads unchanged
- **Breaking changes:** None
- **Migration plan:** Single Alembic revision chained from W0 head
- **Rollback:** `alembic downgrade -1` drops W1 columns/table

## 4) Acceptance Criteria (AC)
- [x] AC-01: `category_id` must be active level-2 on filed upload/create
- [x] AC-02: `access_level` defaults from category; `is_statutory` true for 03.x/04.x
- [x] AC-03: Duplicate approved same category+site+similar title → `duplicate_warning` flag + detail (non-blocking)
- [x] AC-04: `pel_doc_ref` allocated on create when `category_id` set (W0 helper)
- [x] AC-05: submit / approve / reject lifecycle with no self-approve
- [x] AC-06: Approve supersedes prior approved rows with same `pel_doc_ref`; sets `retention_until` from category rule
- [x] AC-07: Signed-url re-checks ACL; logs download/view to `library_document_access_logs`
- [x] AC-08: Forbidden get returns 404 not 403 where feasible

## 5) Testing Evidence
- [x] Unit tests — `tests/unit/test_gov_lib_w1_filing_lifecycle.py` (8 tests)
- [ ] CI — pending PR open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Upload with level-2 category → draft + PEL + filing defaults + duplicate warn if match
- [x] CUJ-02: Submit draft → under_review; reject → draft; approve by different user → approved
- [x] CUJ-03: Self-approve blocked
- [x] CUJ-04: Restricted doc hidden via 404 for unauthorized reader

## 7) Release Plan
- Merge after W0 (#1176) lands on `main` (or merge stacked if campaign allows)
- Staging: filed upload → submit → approve; verify supersession + retention_until + access log

## 8) Rollback Plan
- Revert PR; `alembic downgrade -1`

---

# Gate Checklist
- [x] Gate 0: Scope lock + Change Ledger
- [x] Gate 1: Additive contracts
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
