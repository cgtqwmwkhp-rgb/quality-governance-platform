# Change Ledger (CL-GOV-LIB-W2-RBAC-HSEQ)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W2 — RBAC facets + restricted gates + HSEQ Admin polish
- **User goal:** Staff/manager/admin facets map onto `Role.permissions`; restricted categories (02.08 / 06.03 / 11.03) are gated by `document:restricted:{oh|driver|breach}`; Admin can edit role permissions and manage engineer groups; user-facing copy stays HSEQ.
- **Depends on:** #1176 LIVE (W0+W1 on tip)
- **In scope:** Restricted ACL by taxonomy→permission; list omit for denied docs; facet bundle catalog API; Library Roles Admin page; Engineer Groups Admin page; FE permissions JSON serialization; HSEC→HSEQ test/copy cleanup
- **Out of scope:** Review packs / AI (W3), HSEQ approve→campaign (W4), disposal (W5), named UID allow-lists
- **Feature flag / kill switch:** None — additive ACL + Admin pages; legacy `all_staff` unchanged

## 2) Impact Map
- **Backend:** `document_library_rbac.py`; harden `assert_library_read_access`; list filter in `documents.py`; `GET /document-categories/rbac-catalog`
- **Frontend:** `LibraryRoles.tsx`, `EngineerGroups.tsx`, AdminDashboard tiles, App routes, `usersClient` serialize permissions as JSON string
- **Tests:** `tests/unit/test_gov_lib_w2_rbac.py`; HSEQ group name assertion

## 3) Compatibility & Data Safety
- Additive only; no Alembic
- Restricted without known taxonomy fails closed (404 / omit)
- System roles remain immutable — create overlay roles to edit bundles

## 4) Acceptance Criteria
- [x] AC-01: Facet bundles staff/manager/admin documented + catalog API
- [x] AC-02: 02.08/06.03/11.03 gated by restricted perms (not UID lists)
- [x] AC-03: get + signed-url + list honour ACL
- [x] AC-04: User-facing CUJ copy HSEQ (inbox already HSEQ; test string updated)
- [x] AC-05: Admin Library Roles editor + Engineer Groups page
- [x] AC-06: Unit tests + Change Ledger

## 5) Testing Evidence
- [x] Unit — `test_gov_lib_w2_rbac.py`
- [ ] CI — this PR

## 6) Critical Journeys
- [x] CUJ-01: Staff cannot open restricted OH doc; OH-perm can
- [x] CUJ-02: Driver perm cannot open breach taxonomy
- [x] CUJ-03: Admin manage still bypasses restricted
- [x] CUJ-04: Admin can apply facet bundles on a non-system role

## 7) Release Plan
- Merge to main via programme conveyor; tip deploy

## 8) Rollback Plan
- Revert PR (no migration)

---

# Gate Checklist
- [x] Gate 0: Scope lock + Change Ledger
- [x] Gate 1: Additive contracts
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
