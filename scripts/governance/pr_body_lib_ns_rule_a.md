# Change Ledger (CL-LIB-NS-RULE-A)

## Change Ledger

| Field | Value |
|---|---|
| Wave | Northern Star **W4 / NS-RULE-A** |
| Branch | `feat/lib-ns-rule-a` |
| Base | `origin/main` @ `9ed84ff22` (W2 LIVE) |
| Migration | None — behaviour + validators only |
| Risk | Low–Medium — hardens create path; no schema |
| Reversible | Yes — revert merge |
| ADR | ADR-0023 § Amendment — staged rules (M-08) |
| Deferred | Issue-time blocks (W6), estate warn/queue (W9), R31 |

## 1) Summary

Identity rules R01–R06 / R26 / R29 / R32 are **Block** severity on create.
W3/W2 already made R01–R03 / R06 / R29 hold by construction in the banded
allocator, and R04/R05 via immutability triggers. This PR adds the named
`library_rules.py` module (master-plan landing) and wires hard blocks so a
write cannot silently green:

- Assert R01–R03 on every allocated PEL
- Refuse OPS (and any non-v6 function code) at allocate time via R01
- R26: every create carries `access_level` (taxonomy default or `all_staff`)
- R32: PEL-prefixed upload filenames must match Northern Star grammar

## 2) Impact Map

| Area | Change |
|---|---|
| `src/domain/services/library_rules.py` | New — pack-backed validators |
| `document_category_service.allocate_pel_doc_ref` | Post-allocate `assert_pel_identity` |
| `src/api/routes/documents.py` | R26 + R32 on library upload |
| `tests/unit/test_library_rules.py` | New |
| `tests/unit/test_pel_doc_ref_allocation.py` | OPS allocate now expects R01 block |

## 3) Compatibility & Data Safety

- No alembic; existing rows untouched
- Non-PEL working-title filenames still allowed on wizard allocate path
- OpenAPI: no contract change expected

## Compliance Delta

| Control | Before | After |
| --- | --- | --- |
| Identity rules | Structural only; OPS test gap documented | Named module + hard blocks R01–R03/R26/R32 |
| R01 OPS | Could allocate in harness | Allocator refuses |
| R26 access | Nullable on create without category | Always set + validated |
| M-08 staging | Spec only | Create-time Block lane landed |

## 4) Acceptance Criteria (AC)

- [x] AC-01: `library_rules.py` loads patterns from NS authority pack
- [x] AC-02: `assert_pel_identity` covers R01–R03
- [x] AC-03: Upload enforces R26 + R32 (PEL-prefixed)
- [x] AC-04: Allocator refuses OPS via R01
- [x] AC-05: Unit tests green locally

## 5) Testing Evidence

- [x] `pytest tests/unit/test_library_rules.py tests/unit/test_pel_doc_ref_allocation.py` — 65 passed
- [ ] Full CI on PR
- [ ] Tip-chase STG/PROD after merge

## 6) Critical Journeys

- [x] CUJ-01: Allocate HSEQ L3 → `PEL-HSEQ-3###` passes identity assert
- [x] CUJ-02: Upload PEL-prefixed bad filename → R32 400
- [x] CUJ-03: Create without category → access_level `all_staff` (R26)

## 7) Observability & Ops

- Validation messages include rule ids (`R01`, `R26`, `R32`) for steward triage

## 8) Release Plan

1. Merge after CI green (admin merge authorised)
2. Tip-chase STG then PROD; verify build_sha
3. Next wave: W5b dry-run ingest (W5a already merged)

## 9) Rollback Plan

- **Trigger:** False-positive R32/R26 blocking legitimate uploads
- **Steps:** Revert merge; forward-fix grammar allowlist if needed
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- `northern-star-rules-v6.json` / `northern-star-v6.json` filename_grammar
- Master plan wave W4

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + Change Ledger
- [x] **Gate 1:** No twin SoT; pack is authority
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** STG deploy
- [ ] **Gate 4:** PROD deploy + BUILD_SHA
- [ ] **Gate 5:** DONE = tip LIVE
