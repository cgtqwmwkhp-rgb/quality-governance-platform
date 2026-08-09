# Change Ledger (CL-LIB-WC1-CONTROL-HOLDS)

## 1) Summary
- **Feature / Change name:** Library spine WC-1 — control converge onto the one Register + legal holds that actually refuse (L-01d / L-40)
- **User goal (1–2 lines):** When legal issues a hold on a matter, the documents filed under it stop moving — no revision, no approval, no publish, no obsolete, no disposal — and an HSEQ lead opening the Register sees whether a document is under control and under hold without going to a second page to find out.
- **In scope:** `matter_legal_holds` enforcement across the library and controlled document lifecycle (fail closed); hold scope on the Register row (`documents.legal_matter_reference`) with an `admin:manage` writer and an audit record both ways; control state projected onto the Register; one control record per Register row; library approve/publish written through to the anchored control record in the same transaction; author≠publisher on library publish; one Alembic revision; unit + integration tests
- **Out of scope (adjacent, deliberately not fixed here):** WD-1 "bring under control" wizard FE; the in-app editor; the `approved → published` transition gap (approve freezes the version, so publish cannot then run — CUT-1/WJ-1 lifecycle work); a DB unique index on `controlled_documents.library_document_id` (needs a steward de-dupe first, see §3); multi-matter hold scope per document; WA/WB surfaces (Register export, PEL, 360 layers) are LIVE and untouched
- **Feature flag / kill switch:** None new. Enforcement is unconditional — a hold that can be switched off is not a hold. Behaviour is inert until a matter is filed against a document, so no tenant changes behaviour on deploy.

## 2) Impact Map (what changed)
- **Backend — new:** `src/domain/services/legal_hold_enforcement.py` (the single chokepoint: scope resolution, active-hold read, refusal, SQL predicate for set-based paths)
- **Backend — wired:** `document_version_service.py` (revise/publish, library and controlled; `assert_publisher_is_not_author`); `document_library_lifecycle_service.py` (submit / reject / approve); `document_library_disposal_service.py` (hold predicate inside the eligibility statement); `gkb_control_library_link.py` (batch control-state read + approve/publish write-through)
- **APIs:** `PUT /api/v1/legal-holds/documents/{document_id}` (new, `admin:manage`); `DocumentResponse` gains read-only `controlled_document_id`, `control_status`, `legal_matter_reference`, `legal_hold_active`; `POST /api/v1/document-control/` accepts optional `library_document_id` and refuses an unknown or already-taken anchor; Document Control `PUT /{id}`, `submit-for-approval`, and `approvals/{id}/action` refuse while the anchored Register row is held; `POST /api/v1/documents/{id}/versions` checks the hold **before** the blob upload so a refused revision leaves no orphaned object (the service-level chokepoint is unchanged and still runs)
- **Database:** ONE Alembic revision `20261026_lib_wc1_control_holds` — adds `documents.legal_matter_reference` (nullable `VARCHAR(128)`) and `ix_documents_tenant_legal_matter_reference (tenant_id, legal_matter_reference)`. No new table; `matter_legal_holds` remains the only hold register.
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** `tests/integration/test_lib_wc1_control_holds.py` (18); `tests/unit/test_legal_hold_enforcement.py` (7); `tests/contract/_write_contract_support.py` declares the four new response fields server-owned
- **Docs:** this Change Ledger; the `legal_holds` router docstring no longer says the instructions are unenforced, because they now are
- **Contract baseline:** `openapi-baseline.json` + `docs/contracts/openapi.json` regenerated — additive only (1 new path, 2 new schemas, 4 new optional response fields); `check_openapi_compatibility.py` reports no breaking change

## 3) Compatibility & Data Safety
- **Compatibility strategy:** `legal_matter_reference` is nullable and not backfilled. NULL means "filed under no legal matter", which is a positive fact, not an unknown — so no existing document becomes frozen by deploying this. `library_document_id` on control create stays **optional** so the existing Document Control page keeps working; supplying it is what folds the record onto the Register.
- **Tolerant reader / strict writer applied?** Yes. New response fields are optional and default to null/false; the hold-scope writer is `extra="forbid"` so a misspelled field cannot leave a document outside every hold while returning 200.
- **Breaking changes (behavioural, intended):** an author can no longer publish their own library document (`400 SEPARATION_OF_DUTIES`); a second control record on a Register row already under control is refused (`409 CONTROL_RECORD_EXISTS`); every lifecycle transition on a document under an active hold is refused (`409 LEGAL_HOLD_ACTIVE`).
- **Migration plan:** Additive, nullable column + one composite index. Verified on PostgreSQL from an empty database: `upgrade head` reaches `20261026_lib_wc1_control_holds` as the single head, the column and index exist, and `downgrade -1` followed by `upgrade head` is clean. Both operations are existence-guarded, so a re-run is a no-op. Index creation is not `CONCURRENTLY` — see residual risks.
- **Rollback strategy (DB):** `downgrade -1` drops the index then the column; nothing else reads it. A revert without the downgrade is also safe (the column is simply unused).
- **Why no DB unique index on `controlled_documents.library_document_id`:** migration `20260724_ds_library_control_fk` runs a soft-match backfill that can, in principle, assign the same `library_document_id` to two same-title control rows. Creating a unique index would then fail the deploy on live data. The 1:1 rule is therefore enforced at the write path now, and the index is deferred behind a steward de-dupe rather than shipped as a migration that can block production. Stated plainly rather than claimed as a guarantee we do not have.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Legal hold (spoliation) | `matter_legal_holds` recorded instructions; **no code consumed them** — a held document could be revised, approved, published, obsoleted and hard-deleted | Every one of those paths refuses while an ACTIVE hold covers the document's matter; disposal excludes held rows inside the SQL that selects candidates |
| Hold → document scope | No link existed between a hold and any document | `documents.legal_matter_reference`, written only via `PUT /legal-holds/documents/{id}` under `admin:manage` |
| Who can unfreeze a record | N/A | `admin:manage` only, and both filing and removal are written to the immutable audit trail with previous/new matter and the actor |
| Unreadable hold state | N/A | Fails **closed** — the error propagates, the caller's transaction never commits |
| One Register (D1) | Document Control was a second home; control status was invisible on the Register | Control id + status projected onto the Register row (one batched query per page); no new list, no twin register |
| Two registers disagreeing | Library could publish while the control record still read `draft` | Library approve/publish writes through to the anchored control record in the same transaction |
| Approval attribution | N/A | `approver_id`/`approver_name`/`approved_date` are written by an approval only — a publish moves `status`/`effective_date` and never names the publisher as approver |
| Separation of duties (L-40) | Self-approval refused; **self-publication permitted** straight from draft | Author cannot publish their own document; the author leg of author≠review≠publish is closed at the one place every library publish goes through |
| Silent governance writes | — | Write-through never *creates* a control record: bringing a document under control stays a human filing decision (WD-1) |

## 4) Acceptance Criteria (AC)
- [x] AC-01 (L-40, fail closed): with an ACTIVE hold on the document's matter, revise, publish, approve, submit, reject, metadata edit and mark-obsolete all return `409 LEGAL_HOLD_ACTIVE` naming the matter; the same calls succeed before the hold and again after release
- [x] AC-02 (fail closed on unknown state): when hold state cannot be read the exception propagates and the mutation is refused — never allowed by default; a document with no tenant is refused rather than answered from another tenant's holds
- [x] AC-03 (disposal): a held document is absent from the disposal preview and is not deleted when explicitly named for execution, while an eligible sibling in the same call *is* deleted (so the assertion is not passing on an inert sweep)
- [x] AC-04 (scope is real, not blanket): a hold freezes only its own matter — a document under a different matter, and one filed under none, both proceed; an **empty hold** (matter with no documents filed) freezes nothing
- [x] AC-05 (L-01d, one Register): a control record must anchor to an existing Register row in the caller's tenant (404 otherwise) and a Register row can be under control once only (`409 CONTROL_RECORD_EXISTS`); control id + status are projected on the Register and are `null` when nothing is anchored
- [x] AC-06 (converge, not duplicate): a library publish moves the anchored control record to `published` in the same transaction, and does not overwrite who approved it
- [x] AC-07 (L-40 SoD): the author of a document cannot publish it (`400 SEPARATION_OF_DUTIES`) and the document is not left published; an unattributed publish is not treated as self-publication
- [x] AC-08 (hold scope is not self-releasing): the hold-scope writer requires `admin:manage`, so `document:update` cannot file a record out of the scope of the hold that is blocking it; cross-tenant document ids 404
- [x] AC-09 (no twin): no new table, no second control register, no second Confirm Queue; `validate_library_anti_dupe` reports 0 coverage twins and 0 freetext violations
- [x] AC-10 (refusal without side effects): a revision attempt on a held document that carries a file is refused **before** the upload — storage is never called, so no orphaned blob is left behind by the refusal

## 5) Testing Evidence (link to runs)
Everything below was run and observed locally at this branch tip. Runs on both
dialects are listed separately because the default harness is SQLite and CI is
PostgreSQL, and the FK behaviour differs between them.
- [x] WC-1 suites (`tests/integration/test_lib_wc1_control_holds.py` + `tests/unit/test_legal_hold_enforcement.py`) — **27 passed** on SQLite **and 27 passed** on PostgreSQL
- [x] Full unit + contract suites — **6468 passed, 0 failed** (79 skipped, 59 xfailed — the skips are pre-existing and this run is not evidence for them)
- [x] Full integration suite on PostgreSQL — **1117 passed, 0 failed, 0 errors** (1103 in the main pass, plus the 12 schema-parity tests re-run without `PYTHONPATH=.`: that flag makes the repo's own `alembic/` migrations package shadow the installed `alembic` for the subprocess those tests spawn, which is a local invocation artefact and not a code defect — `PYTHONPATH=. alembic --version` reproduces it on a clean checkout)
- [x] Empty-database migration proof on PostgreSQL: `alembic heads` = exactly `['20261026_lib_wc1_control_holds']`; `upgrade head` from an empty database; `\d documents` shows `legal_matter_reference character varying(128)` and `ix_documents_tenant_legal_matter_reference btree (tenant_id, legal_matter_reference)`; `alembic_version` = `20261026_lib_wc1_control_holds`; `downgrade -1` then `upgrade head` again both clean (existence-guarded, so a re-run is a no-op)
- [x] `black --check` / `isort --check-only` / `flake8` (0) / `mypy` (`Success: no issues found in 594 source files`)
- [x] Governance gates: `validate_migration_naming` (0 violations), `validate_schema_constraints` (0 critical), `validate_tenant_id_not_null` (0 critical), `validate_library_anti_dupe` (0 critical), `validate_error_code_coverage` (pass), `validate_registries` (pass), `validate_openapi_contract` (819 paths), `check_openapi_compatibility` (additive only), `validate_write_schema_extra_forbid_ratchet` and `validate_audit_trail_coverage_ratchet` (within baseline)
- [x] Head-pin tests in `test_job_lifecycle_ux_w4/w5.py` advanced to the new head (invariant unchanged — see below)
- [ ] Full CI — on PR (the source of truth for the sharded runs and the CI dialect)
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

**Review findings folded in.** Bugbot found two real gaps after push. First: the library revise route uploads the new file to blob storage before reaching the service-level guard, so a refused revision of a held document still left an orphaned object. Fixed at the route (pre-upload check retained alongside the service chokepoint) and covered by AC-10. The controlled revise route takes no file, so it does not have the same shape. Second: Document Control `PUT /{id}`, `submit-for-approval`, and `approvals/{id}/action` mutated anchored control records without `assert_controlled_document_not_held`; wired the guard on all three and covered by an integration test.

**Two existing tests were edited; neither assertion was weakened.** `test_job_lifecycle_ux_w4.py` / `_w5.py` pin the *literal* current Alembic head to prove the chain has not branched. Adding any migration makes that literal stale — the test's own comment says "Tip head advances with later migrations" and WA-2 updated it the same way. The invariant (exactly one head) is unchanged; only the expected head advances to `20261026_lib_wc1_control_holds`.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01 (hold arrives mid-life): legal issues a hold on a matter; an HSEQ lead who was about to revise a document filed under it is refused with the matter named, sees `legal_hold_active` on the Register and Detail, and can proceed again only once the hold is released
- [x] CUJ-02 (retention sweep meets a hold): a retention-due obsolete document under hold never appears in the disposal queue and is not deleted when named for execution, while an eligible document in the same batch is disposed as normal
- [x] CUJ-03 (bring a document under control): an admin anchors a control record to a Register row; the Register row then reports its control id and status, and a second attempt to control the same row is refused
- [x] CUJ-04 (two registers agree): a document approved and published on the Register no longer leaves Document Control reading `draft`; the control record moves in the same transaction, and the person who approved it is still named as approver after the publish
- [x] CUJ-05 (separation of duties): an author submits their own document and tries to publish it, and is refused; a second person publishes it

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** No new metric. Refusals surface as `409 LEGAL_HOLD_ACTIVE` / `400 SEPARATION_OF_DUTIES` in the existing error envelope and request log. Hold-scope changes emit `document.legal_hold_scope_changed` into the immutable audit trail (`audit_log_entries`), which is the searchable record of who took a document out from under a matter.
- **Query cost:** the Register list adds exactly two queries per page (control state, hold verdict), both batched over the visible ids — the list stays off the N+1 path it already avoids for its other joins.
- **Runbook updates:** to freeze records, create the hold (`POST /api/v1/legal-holds`) **and** file each document under that matter (`PUT /api/v1/legal-holds/documents/{id}`). A hold with nothing filed against it freezes nothing — that is by design and is now testable.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Ship with tip. Migration runs on deploy; additive and nullable, so no data motion and no backfill window.
- **Canary plan:** N/A — enforcement is inert until a matter is filed against a document, so the blast radius on deploy is zero. First real exercise is the runbook step above on staging.
- **DONE bar:** Conveyor marks WC-1 PROD/DONE only after the tip SHA is LIVE on ACA and health is verified on the prod FQDN.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** legitimate lifecycle transitions refused for documents that are not held; the Register list regressing on latency; publish refused for a document whose author is not the publisher.
- **Rollback steps:** Revert the merge and redeploy the prior tip. The column can be left in place (unused and nullable); if it must go, run `alembic downgrade -1`, which drops the index then the column. Note that reverting **re-opens** the spoliation gap: holds go back to being recorded and unenforced, so a revert should be paired with an out-of-band instruction to stewards not to revise held records.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): linked once PR checks complete (the source of truth for the sharded runs)
- Migration evidence: empty-database `alembic upgrade head` + `downgrade -1` + re-`upgrade` on PostgreSQL; `\d documents` showing the column and `ix_documents_tenant_legal_matter_reference`; `alembic_version` = `20261026_lib_wc1_control_holds`; `alembic heads` = one head
- Test evidence: WC-1 27 passed on SQLite and 27 on PostgreSQL; 6468 unit+contract passed; 1117 integration passed on PostgreSQL with zero failures and zero errors
- Contract evidence: `check_openapi_compatibility.py` — 1 new endpoint, 2 new schemas, no breaking change
- Staging deploy evidence: after merge tip chase
- Canary evidence (if applicable): N/A
- Acceptance notes: L-01d / L-40 from `library-world-class-ux-plan`; conveyor WC-1 (depends WB-1 PROD). Adjacent held deliberately: WD-1 wizard, editor, `approved → published` transition, `controlled_documents.library_document_id` unique index, multi-matter hold scope.
- **Decision pending:** author≠publisher on library publish closes the self-publish escape hatch (approve already refuses self-approval on main). Confirm keep-in-WC-1 vs strip to a follow-up PR before merge if single-admin tenants must keep author-publish.

## Residual risks (disclosed, not hidden)
1. **Empty hold.** A hold on a matter with no documents filed against it freezes nothing. This is the state every hold starts in — the instruction arrives before anyone files records — so it is asserted as correct behaviour (AC-04) rather than patched. Mitigation is procedural and is now in the runbook: issuing a hold is two steps, not one.
2. **Concurrent revise (read-committed race).** A hold committed by another transaction *after* the guard's SELECT cannot retroactively refuse the in-flight call, so a draft version row can be opened in a window one statement wide. The gates downstream — approve and publish — each re-run the check, so the outcome a hold exists to prevent (a held record reaching a new published state) is still refused. The prior published version keeps its own immutable file path, so the evidence chain is not broken. A complete fix needs the hold-creation path to lock the documents it covers, or a DB trigger; both are larger than this slice.
3. **One matter per document.** A document needed by a second matter is held through the matter it is filed under; the column cannot record both. Holding under one matter still refuses the write, so this fails closed, but it cannot represent overlapping matters. A scope table is the real fix.
4. **Migration on production.** `CREATE INDEX` on `documents` is not `CONCURRENTLY` (Alembic runs migrations in a transaction here, which forbids it), so it takes a brief ACCESS EXCLUSIVE lock on `documents` while it builds. It is a two-column index on a table of governance documents rather than a high-volume event table, so the expected window is short — but it is a lock on a hot table during deploy, and worth knowing before a busy-hours release.
5. **Pre-existing unanchored control records.** Control records created before WC-1 with no `library_document_id` cannot be frozen through a Register row, because there is no Register row carrying the matter. New unanchored records are not created by the folded path, and the existing count is already reported by `count_unlinked_controlled`.
6. **Duplicate anchors from the 20260724 soft-match backfill.** If two control records share a `library_document_id` on some deployment, the Register projection deterministically shows the lowest id. The write path now refuses new duplicates; removing the existing possibility needs the steward de-dupe described in §3.
7. **Publish without approval remains reachable.** WC-1 closes the *author* leg (an author cannot publish their own work) but does not require an approval before publish, because `approve_document` marks the version immutable and publish can then find no draft to publish. Making `approved → published` work is a lifecycle change (CUT-1/WJ-1), deliberately not attempted inside a migration+wire slice.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — one Alembic revision (single head, up+down proven on PostgreSQL from an empty database); one hold register; control folded onto the one Register; no twin register and no second Confirm Queue; OpenAPI additive only
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge; create a hold, file a document under it, confirm revise is refused and release restores it
- [x] **Gate 4:** Canary healthy (if used) — N/A (inert until a matter is filed)
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE on ACA and prod health verified before DONE
