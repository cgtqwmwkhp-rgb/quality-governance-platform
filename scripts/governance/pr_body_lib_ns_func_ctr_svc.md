# Change Ledger (CL-LIB-NS-FUNC-CTR-SVC)

## Change Ledger

| Field | Value |
|---|---|
| Wave | Northern Star **W2 / NS-FUNC** (after W3 NS-1 banded PEL on tip) |
| Branch | `feat/lib-ns-func-ctr-svc` |
| Base | `origin/main` @ `6af0712be` (NS-1 merged) |
| Migration | `20261028_lib_ns_func_ctr_svc` on `20261027_lib_ns1_banded_pel` (single head) |
| Risk | Low–Medium — vocabulary upsert + inactive OPS; no reference rewrite |
| Reversible | Partial — downgrade reactivates OPS / deactivates CTR+SVC; does not delete rows |
| ADR | ADR-0023 § Amendment — Twelve functions / W2 reseed |
| Deferred | `owner_role` (R16), staged R-rules hardness, explorer, nightly |

## 1) Summary

Northern Star v6 splits the WA-2 **OPS** fold into **CTR** (Control Room) and
**SVC** (Service Delivery / workshop). Deploy runs `alembic upgrade head` only,
so this PR lands one migration that upserts `functions.json` into
`document_functions`, forces OPS inactive, and seeds missing banded PEL
counters for the new codes — without resetting any existing `next_seq` (R29).

OPS stays as an inactive row so issued `PEL-OPS-####` strings remain resolvable.
Forward filing already refuses inactive codes (`resolve_function_code` /
`allocate_pel_doc_ref`) and the functions list hides them by default.

## 2) Impact Map (what changed)

| Area | Change |
|---|---|
| `specs/governance-library/functions.json` | v1.1 — CTR+SVC active; OPS withdrawn inactive; FLT/TECH boundaries updated |
| `src/domain/services/document_category_seed_data.py` | `EXPECTED_FUNCTION_COUNT = 13` (12 NS + withdrawn OPS) |
| `alembic/versions/20261028_lib_ns_func_ctr_svc.py` | Upsert + OPS inactive + banded counter seed |
| `docs/adr/ADR-0023-…` | Amendment §3 notes W2 migration id |
| `tests/unit/test_document_category_seed.py` | Expect CTR/SVC active, OPS inactive |
| `tests/unit/test_pel_doc_ref_allocation.py` | Comment aligned with W2 landed |

## 3) Compatibility & Data Safety

- **No reference rewrite.** Existing `documents.pel_doc_ref` values unchanged.
- **No counter reset.** New (function, band) rows start at 1; existing counters untouched.
- **API additive.** Function list shape unchanged; default filter already hides inactive.
- **OpenAPI:** no contract change expected.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Function vocabulary | 11 codes incl. active OPS | 12 NS active (CTR+SVC) + OPS inactive |
| R01 allow-list | Spec has CTR/SVC; seed still OPS | Seed matches NS; OPS cannot accept new filings |
| R29 append-only | — | Issued PEL-OPS-#### still resolve via inactive OPS row |
| Deploy path | Seed script not on startup | Alembic upsert lands vocabulary on STG/PROD |

## 4) Acceptance Criteria (AC)

- [x] AC-01: `functions.json` lists CTR + SVC active and OPS `active: false`
- [x] AC-02: `EXPECTED_FUNCTION_COUNT` matches seed length (13)
- [x] AC-03: Alembic `20261028_lib_ns_func_ctr_svc` revises NS-1 head only
- [x] AC-04: Unit tests pin CTR/SVC active and OPS inactive after seed
- [x] AC-05: No silent renumber of issued PEL refs; no OpenAPI baseline churn expected

## 5) Testing Evidence (link to runs)

- [ ] Unit seed tests — local / CI
- [ ] Full CI — on PR
- [ ] Staging / Prod — tip chase after merge (BUILD_SHA + health)

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Filing picker / `list_document_functions` default hides OPS
- [x] CUJ-02: Allocating against OPS raises inactive ValidationError (existing guard)
- [x] CUJ-03: CTR/SVC get banded counters for levels 1–5 without resetting others

## 7) Observability & Ops

- None beyond existing migration logs on container startup (`alembic upgrade head`)

## 8) Release Plan

1. Merge after CI green (admin merge authorised).
2. Tip-chase **Deploy to Azure Staging** then **Deploy to Azure Production**.
3. Verify `/api/v1/meta/version` `build_sha` matches tip; health 200.
4. Optional: admin reseed endpoint confirms OPS inactive / CTR+SVC present.

## 9) Rollback Plan (Mandatory)

- **Trigger:** CTR/SVC wrong; filing broken for service docs
- **Steps:** Revert merge (downgrade reactivates OPS / deactivates CTR+SVC) **or** forward-fix seed JSON + new alembic
- **Owner:** Platform Engineering — David Harris
- **Note:** Do not delete CTR/SVC rows if any PEL-CTR/SVC refs already issued

## 10) Evidence Pack

- Authority: `northern-star-v6.json` / `northern-star-rules-v6.json`
- Master plan: `library-v6-northern-star-master-plan` wave W2
- Prior: NS-1 #1678 banded counters (required parent)

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Single alembic head; R29 respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** STG deploy success
- [ ] **Gate 4:** PROD deploy success + BUILD_SHA match
- [ ] **Gate 5:** DONE = tip LIVE
