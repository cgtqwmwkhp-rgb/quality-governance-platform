# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Portal + staff Near Miss live Admin Contracts/Lookups catalogs
- **User goal:** Portal Near Miss/Incident/Complaint Contract and Role dropdowns read live Admin Contracts and Lookups (workforce_roles → roles). No silent hardcoded UKPN/role lists. Staff Near Miss create uses the same Contracts list.
- **In scope:** AC-01..AC-06
- **Out of scope:** Canonical FKs; Customers→portal Contract merge; Safety locations unification; due_soon notify
- **Feature flag / kill switch:** N/A — removes fake fallback happy path

## 2) Impact Map
- **Frontend:** `PortalDynamicForm.tsx`, `NearMisses.tsx`
- **Backend / APIs / DB:** None (consumes existing Admin Contracts + Lookups GET)

## 3) Compatibility & Data Safety
- Submit still stores stable contract/role **codes** as free text (historical reports readable)
- Template structure may still use FALLBACK_TEMPLATES only when published template missing
- Catalog API failure shows error/empty — never silent FALLBACK_CONTRACTS/ROLES

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin Contracts edits feed portal Contract dropdown
- [x] AC-02: workforce_roles (else roles) feed portal Role dropdown
- [x] AC-03: No happy-path FALLBACK_CONTRACTS / FALLBACK_ROLES
- [x] AC-04: Submit still sends code strings
- [x] AC-05: API failure shows empty+error, never silent fake list
- [x] AC-06: Staff Near Miss contract field uses live Contracts list

## 5) Testing Evidence
- [x] Typecheck / unit as available in CI

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Portal Near Miss Select Contract reflects Admin Contracts
- [x] CUJ-02: Staff Near Miss create picks contract code from Admin list

## 7) Observability & Ops
- No change

## 8) Release Plan
- Staging: edit Admin contract label → confirm portal dropdown; tip==LIVE after merge

## 9) Rollback Plan
- **Rollback trigger:** Portal forms cannot load contracts for authenticated users
- **Rollback steps:** Revert this commit/deploy on main
- **Owner:** Platform team

## 10) Evidence Pack
- CI linked on PR

---

# Gate Checklist
- [x] Gate 0: Scope lock + AC defined + Change Ledger complete
- [x] Gate 1: API/Data/UX contracts approved (existing Admin GET endpoints)
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [ ] Gate 4: Canary (N/A)
- [x] Gate 5: Production verification plan ready
