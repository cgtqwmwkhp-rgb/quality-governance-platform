# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Compliance & cross-standard mappings hardening (wave 1)
- **User goal (1-2 lines):** Tenant-scoped canonical enrichment for ISO compliance standards; bounded cross-standard list reads; validated mapping types; observability on read failures; resilient ISO Compliance page load when some APIs fail.
- **In scope:** `compliance.py` (`_load_canonical_standard_rows`), `cross_standard_mappings.py`, `ComplianceEvidence.tsx`, `client.ts` cross-standard API, unit tests
- **Out of scope:** OpenAPI baseline regeneration (additive query params only), pagination response wrapper, axios toast suppression
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `ComplianceEvidence.tsx` (Promise.allSettled, partial-load banner), `client.ts` (limit/offset query params)
- **Backend:** `src/api/routes/compliance.py`, `src/api/routes/cross_standard_mappings.py`
- **APIs:** `GET /api/v1/cross-standard-mappings` optional `limit` (1–500), `offset` (≥0); `mapping_type` allowlist on create/update
- **Database:** None
- **Workflows:** None

## 3) Compatibility & Data Safety
- **Strategy:** Additive query params; default list behaviour unchanged when `limit`/`offset` omitted
- **Breaking changes:** Invalid `mapping_type` strings now rejected at validation (422) — clients sending garbage types must use equivalent|partial|related
- **Rollback:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Tenant-scoped `Standard` / `Clause` / `IMSRequirement` enrichment for `list_standards`
- [x] AC-02: Cross-standard list supports optional limit/offset; errors emit metric + empty list (existing behaviour)
- [x] AC-03: Unit tests pass for compliance spine and cross-standard integration
- [x] AC-04: Frontend build passes

## 5) Testing Evidence (link to runs)
- [x] Local: pytest wave2 compliance + cross-standard; `npm run build`
- [x] CI: after PR open — `make pr-ready`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: ISO Compliance Evidence Center loads with partial data if one compliance sub-API fails
- [x] CUJ-02: Cross-standard mappings for a clause capped at 500 rows client-side request
- [x] CUJ-03: Invalid mapping type rejected at API boundary

## 7) Observability & Ops
- **Metrics:** `cross_standard_mappings.list_error`, `cross_standard_mappings.standards_list_error`

## 8) Release Plan
- Merge → CI → staging → production per standard pipeline

## 9) Rollback Plan
- Revert merge commit; no migration

## 10) Evidence Pack
- CI run linked post-merge

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Change Ledger complete
- [x] **Gate 1:** API contract additive-only for list query params
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification after deploy
- [ ] **Gate 4:** N/A
- [x] **Gate 5:** Prod promotion follows existing governed chain
