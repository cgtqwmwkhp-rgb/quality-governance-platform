# Change Ledger (CL-LIB-WA2-FUNCTIONS-PEL)

## 1) Summary
- **Feature / Change name:** Library SECOND belt WA-2 — Functions seed + PEL allocator on the function axis (ADR-0023)
- **User goal (1–2 lines):** A filed document's reference identifies its owning function (`PEL-IT-0014`), not the taxonomy path it happens to sit in — so an information-security policy still files to `01.01 Policies` but reads `PEL-IT-####`. Once issued, the reference and the function behind it can never be rewritten.
- **In scope:** `document_functions` table + 11-code seed from `specs/governance-library/functions.json`; `pel_doc_ref_counters` re-keyed category → function; `documents.function_id`; allocator returns `PEL-<FUNCTION>-<SEQ:04d>`; PEL/function immutability (ORM guard + PostgreSQL trigger); `GET /api/v1/document-categories/functions`; optional `function_code` on the three create paths; one Alembic migration
- **Out of scope:** Function picker UI and "confirm Function" wizard (WD-1); Function column on the Register (WA-1 shipped without it; deliberately not added here); bulk derivation of functions for the 309-document legacy estate; category → default-function mapping (see Compatibility below — ADR-0023 does not resolve the HSEQ/FAC boundary, so it is not invented here); owner-roles normalisation (Wave W6, unmerged); machine-readable retention
- **Feature flag / kill switch:** None. Every new request field is optional and every new column is nullable, so the change is inert for callers that do not send `function_code`.

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** `document_library.py` (`DocumentFunction`; `PelDocRefCounter.function_id`); `document.py` (`function_id` + immutability listeners); `document_category_seed_data.py` (`load_library_functions`); `document_category_service.py` (function seed, `resolve_function_code`, allocator rewrite); `documents.py` upload; `compliance_schedule_filing_service.py`; `compliance_schedule_fra_ocr_service.py`; `document_categories.py`; `compliance_schedule.py` routes
- **APIs:** `GET /api/v1/document-categories/functions` (new, `document:read`); optional `function_code` on `POST /documents/upload`, `POST /compliance-schedule/records/{id}/file`, `POST /compliance-schedule/fra-ocr/drafts/{id}/file`; `SeedResultResponse` gains `functions_created` / `functions_updated` / `total_functions` (additive)
- **Database:** `20261025_lib_wa2_functions_pel` — creates `document_functions`; re-keys `pel_doc_ref_counters` from `category_id` to `function_id` (RESTRICT); adds `documents.function_id` (RESTRICT); installs `trg_documents_pel_doc_ref_immutable` on PostgreSQL. Single Alembic head.
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** `test_pel_doc_ref_allocation.py` (ported to the function axis, plus four-digit/overflow/resolver cases); `test_pel_doc_ref_immutability.py` (new); `test_document_category_seed.py` (function seed + counter-never-reset); `test_compliance_schedule_filing_api.py` (function-derived ref, no-function path, unknown-code refusal); head pins in `test_job_lifecycle_ux_w4/w5.py`; cascade register in `test_delete_cascade_audit_visibility.py`
- **Docs:** `specs/governance-library/functions.json`, spec-pack README, `docs/governance/tenant_id_catalog_exceptions.json`, this Change Ledger
- **Contract baseline:** `openapi-baseline.json` refreshed. The diff is only the surface listed under APIs above — one new path, one new schema, `function_code` added as an optional property to three request bodies, and three counts on `SeedResultResponse`. Those counts are what `check_openapi_compatibility.py` reports as breaking: it applies its "new required field" rule to every schema, and cannot tell that `SeedResultResponse` is only ever a response body, where a new required field is additive for the client. The checker's request/response blindness is a real gap but a shared gate touching every PR, so it is noted rather than changed here.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** `function_code` is optional on every create path. A caller that omits it still files the document — it simply carries no `pel_doc_ref` until a function is confirmed, which is a state WA-1's Register already renders (DOC lead, Hyperlink never blank). An unrecognised code is refused rather than treated as "no function".
- **Breaking changes:** One behavioural change, taken deliberately. Before WA-2 the two compliance-schedule filing paths always allocated a PEL from the category. They now allocate only when the caller supplies a function. Deriving one from the category would have to resolve the HSEQ/FAC boundary that ADR-0023 explicitly leaves open (H&S owns "the entire assessment estate"; Facilities owns "site risk assessments … fire"), and a guess there prints an immutable wrong prefix on a fire risk assessment. Failing closed is the ADR's own stated mitigation. The FE can start sending `function_code` with no further backend work.
- **Migration plan:** Forward-only, one head, applied and reverted end-to-end against a scratch PostgreSQL. `document_functions` is created and seeded additively (existing codes are never rewritten — a code is the literal prefix of every reference it has issued). The old per-category counter rows are dropped rather than mapped: there is no meaningful 73 → 11 mapping, and carrying a category's `next_seq` onto a function would skip or re-issue numbers. Every function starts at `0001`. **No `documents.pel_doc_ref` value is read, rewritten, renumbered or deleted, on the way up or the way down.** References already issued under the retired `PEL-<SECTION>-<SUB>-<SEQ>` form stay verbatim and cannot collide with the new form, which carries no numeric subcategory group.
- **Rollback strategy (DB):** `alembic downgrade -1` drops the trigger, `documents.function_id` and `document_functions`, and restores the Wave W0 category-keyed counter table. Verified: issued `pel_doc_ref` values survive the downgrade untouched. Pre-WA-2 sequence numbers are not resurrected, deliberately — inventing them would let the retired scheme re-issue a reference a document already carries.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Reference scheme (D2 / D16) | `PEL-<SECTION>-<SUB>-<SEQ>` derived from the category; all 48 policies would share `PEL-GOV-01` | `PEL-<FUNCTION>-<SEQ:04d>` per ADR-0023; category classifies, reference identifies |
| Category ≠ Function (D2) | One axis; the taxonomy path was the reference | Two axes recorded independently — `category_id` and `function_id` on the same row |
| Reference immutability | Convention only; any `UPDATE` could rewrite `pel_doc_ref` | ORM guard refuses a rewrite, and `trg_documents_pel_doc_ref_immutable` refuses it in the database including raw SQL. NULL → value stays allowed |
| AI / system never silent-writes Function | Category-derived prefix was written with no human confirmation | No function is inferred anywhere. Absent an explicit code the document files with no reference |
| Sequence exhaustion | Three digits; HSEQ holds 226 documents on day one | Four digits, and the width is a floor — allocation 10000 formats as `PEL-HSEQ-10000` rather than wrapping onto an issued number |
| One allocator, no twin (enhance ≠ replicate) | `allocate_pel_doc_ref(db, category_id)` | Same function, same table, re-keyed. No second allocator, no parallel counter home, no `document_coverage_claims` |
| Counter deletion | `document_categories → pel_doc_ref_counters` was `ON DELETE CASCADE` — deleting a parent silently reset a sequence | `ON DELETE RESTRICT` on both the counter and `documents.function_id`; a function in use cannot be deleted. Removed from the invisible-cascade register |
| Authorisation posture | — | New reader checks `document:read` rather than joining the authenticated-only debt list (census ceiling unchanged at 467) |

## 4) Acceptance Criteria (AC)
- [x] AC-01 (L-01b): `document_functions` exists and seeds the 11 ADR-0023 codes idempotently from `functions.json`; a duplicate code in the spec is refused
- [x] AC-02 (L-01c): the PEL counter is one row per function, and a reseed never resets or bumps an existing counter
- [x] AC-03: `allocate_pel_doc_ref` returns `PEL-<FUNCTION>-<SEQ:04d>` and remains atomic — 25 concurrent allocations produce 25 distinct, gapless references, and two functions never cross-contaminate
- [x] AC-04: an allocated `pel_doc_ref` and `function_id` cannot be rewritten or nulled, in the ORM and in PostgreSQL; NULL → value remains allowed
- [x] AC-05: create paths accept an optional `function_code`; an unknown or inactive code is refused; an absent code files the document with no reference rather than a derived one
- [x] AC-06: exactly one Alembic head; upgrade, downgrade and re-upgrade all verified against PostgreSQL with issued references preserved
- [x] AC-07: no twin table, no second allocator, no Function column added to the Register (WD-1 owns the picker) — library anti-dupe gate reports 0 critical

## 5) Testing Evidence (link to runs)
- [x] `pytest tests/unit` — 5999 passed, 11 pre-existing skips, 0 failed (local)
- [x] `pytest tests/integration/test_compliance_schedule_filing_api.py` — 24 passed (local)
- [x] `pytest tests/integration/test_route_authorisation_census.py` — 11 passed (local)
- [x] `alembic upgrade head` → `downgrade -1` → `upgrade head` on a scratch PostgreSQL 
- [x] Trigger proven by raw SQL: rewrite refused, null refused, function rewrite refused, unrelated update allowed, NULL → value allowed, delete-in-use refused
- [x] `python3 scripts/governance/library/anti_dupe_gate.py` — 0 critical, 0 advisory
- [x] `alembic check` + `validate_alembic_drift_ratchet.py` on a scratch PostgreSQL — no new suppressed drift. First run caught a real omission: `TimestampMixin` declares `created_at` indexed and the migration did not create it, so `ix_document_functions_created_at` was added rather than the baseline widened
- [x] `check_openapi_compatibility.py` against the refreshed baseline — pass
- [x] `black --check` / `isort --check-only` / `flake8` clean
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: filer uploads with `function_code=IT` → document carries `PEL-IT-0001` and `function_id`, and appears on the Register with PEL leading
- [x] CUJ-02: filer uploads without a function → document is created, openable, and leads with its `DOC-YYYY-####` reference; no reference is invented
- [x] CUJ-03: an unknown function code is refused before any file is copied to storage
- [x] CUJ-04: ownership of information security moves IT → DP; the existing `PEL-IT-0014` reference is untouched and the attempted rewrite is refused
- [x] CUJ-05: an admin reseed after a `functions.json` edit updates names without resetting any counter or re-issuing a reference

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None new. Filing audit events now carry `function_code` alongside `category_id`.
- **Runbook updates:** After deploy, run `python -m scripts.governance.library.seed_document_categories` only if the migration's seed was skipped (it is PostgreSQL-only and additive; the reseed is safe at any time and never resets a counter).

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Ship with tip; no flag flip. The migration seeds the 11 functions on apply.
- **Canary plan:** N/A — additive schema, optional request fields
- **DONE bar:** Conveyor marks WA-2 PROD/DONE only after the tip SHA is LIVE on ACA and health is verified

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Filing regressions, unexpected refusals from the immutability trigger, or contention on a function counter
- **Rollback steps:** Revert the merge and redeploy the prior tip; run `alembic downgrade -1` only if the schema must also go back. The downgrade is verified to leave every issued `pel_doc_ref` intact, so a re-upgrade re-creates the functions and counters without touching existing references. Because all new fields are optional and nullable, an application-only revert is sufficient in most cases and leaves the schema harmlessly ahead.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: After merge tip chase
- Canary evidence (if applicable): N/A
- Acceptance notes: ADR-0023 is the authority for the 11 codes, the four-digit sequence, the retained `PEL-` company prefix, and the rule that a function is fixed at filing. `functions.json` is the seed SSOT; `taxonomy.json` remains the category SSOT and its `ref_prefix` is now a filing default only.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — one allocator re-keyed, no twin tables, new reader permission-gated
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge; migration applies and reverts cleanly on PostgreSQL
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE before DONE
