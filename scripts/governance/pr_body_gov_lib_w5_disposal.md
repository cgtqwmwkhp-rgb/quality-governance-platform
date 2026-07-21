# Change Ledger (CL-GOV-LIB-W5-DISPOSAL)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W5 — retention disposal queue and Policy CRUD freeze
- **User goal:** Give HSEQ an auditable, dry-run-first queue of retention-due inactive library files; prevent new legacy Policy records from creating a second document stack.
- **Depends on:** W1 filing lifecycle (`retention_until`), W4a HSEQ campaign offer, W4b campaign CI
- **In scope:** Tenant-scoped disposal preview; explicit-ID hard disposal behind a default-off flag; policy write freeze and UI migration guidance; unit acceptance tests.
- **Out of scope:** Parsing free-text category retention rules into dates; automatic scheduling; disposal of active/published documents; a new document store.
- **Feature flag / kill switch:** `LIBRARY_DISPOSAL_EXECUTE=false` (default). `POST /documents/admin/disposal/execute` returns 403 until enabled.

## 2) Impact Map
- **Frontend:** Legacy Policy page retains read-only history and directs users to Governance Library, Document Control, and HSEQ Campaigns; create UI removed.
- **Backend:** `document_library_disposal_service.py`; document disposal preview/execute routes; legacy policy write routes frozen.
- **APIs:** `GET /api/v1/documents/admin/disposal`; `POST /api/v1/documents/admin/disposal/execute`.
- **Schemas/contracts:** Additive disposal schemas. Existing policy write APIs now return 410 with actionable migration guidance.
- **Database:** No migration. Reuses `documents.retention_until`, lifecycle status, and `document_categories.retention_rule`.
- **Observability:** Metrics `library.disposal_queue.previewed`, `.execution_blocked`, and `.executed`.

## 3) Compatibility & Data Safety
- Preview is read-only and tenant-scoped. Candidates must have elapsed explicit `retention_until`, an inactive lifecycle status (`archived`, `obsolete`, `retired`, or `superseded`), and no campaign/control/discussion/quiz provenance dependencies.
- Category `retention_rule` remains informational provenance; W5 does not infer a destruction date from free text.
- Execution requires both `admin:manage` and `LIBRARY_DISPOSAL_EXECUTE=true`, plus explicitly supplied IDs. Non-candidates are skipped.
- Hard disposal deletes the governed document and its blob only after the flag is enabled. Default production behaviour is no destructive action.
- Rollback: set `LIBRARY_DISPOSAL_EXECUTE=false` immediately, then revert this PR for route/UI removal. Disposed data requires storage/database recovery procedures.

## 4) Acceptance Criteria
- [x] AC-01: Admin dry-run lists only current-tenant documents with elapsed `retention_until`.
- [x] AC-02: Preview excludes published/active lifecycle documents even when their date has elapsed.
- [x] AC-03: Preview returns category retention-rule provenance and is always `dry_run=true`.
- [x] AC-04: Execute endpoint is 403 by default with an explicit `LIBRARY_DISPOSAL_EXECUTE` remediation message.
- [x] AC-05: Enabled execution accepts explicit IDs only and deletes only currently eligible tenant documents.
- [x] AC-06: New legacy Policy create/update/delete operations return 410 and point to Library, Control, and Campaigns.
- [x] AC-07: Policy UI removes the create path and displays migration links/guidance.
- [x] AC-08: SPEC §13-style focused unit acceptance coverage is added.

## 5) Testing Evidence
- [x] Unit: `pytest tests/unit/test_gov_lib_w5_disposal_policy_freeze.py`
- [ ] CI: PR checks
- [ ] Staging: verify preview against a controlled retention-due retired document; keep execute flag off.

## 6) Critical Journeys
- [x] CUJ-01: HSEQ admin previews retention queue → sees only due, inactive documents with rule provenance.
- [x] CUJ-02: HSEQ admin attempts execute with default config → receives safe 403; no rows or blobs mutate.
- [x] CUJ-03: Release operator enables flag, explicitly selects an eligible ID → only that valid tenant candidate is hard-disposed.
- [x] CUJ-04: Quality user selects legacy Policy “new” path → receives Library / Document Control / HSEQ Campaigns guidance; no new Policy row is created.

## 7) Rollback Plan
- **Owner:** Platform / HSEQ release operator
- **Rollback steps:**
  1. Set `LIBRARY_DISPOSAL_EXECUTE=false` immediately (blocks all execute paths).
  2. Revert this PR / redeploy prior SHA to remove disposal routes and restore Policy write APIs if needed.
  3. For any hard-disposed documents, restore from DB/blob backup per storage recovery procedure (disposal is irreversible without recovery).

## 8) Observability & Operations
- **Metrics:** Queue preview count, blocked execution count, and enabled execution count are emitted under `library.disposal_queue.*`.
- **Logs:** Existing FastAPI error handling captures forbidden execution attempts; storage failures surface through the existing storage service.
- **Alerts:** Alert on any non-zero `.executed` metric until retention disposal has an approved operational runbook.
- **Runbook:** Start with `GET .../admin/disposal`; review references, lifecycle status, and rule text; obtain explicit approval before setting the execution flag; execute explicit IDs only; retain request/audit evidence.

## 9) Release Plan
- **Staging:** Confirm preview is tenant-isolated and no storage calls occur. Keep flag false.
- **Canary:** If execution is authorised, enable the flag briefly for one approved, recoverable test candidate and collect audit evidence.
- **Production:** Default flag remains false. Verify dashboard/metric ingestion for preview and blocked paths.

## 10) Evidence Pack
- Unit command: `pytest tests/unit/test_gov_lib_w5_disposal_policy_freeze.py`
- Format command: `black --check src tests && isort --check-only src tests`
- Type-ignore ceiling: verify repository count remains at or below 216.
- CI / staging / approval evidence: attach to this PR before merge.

---

# Gate Checklist
- [x] **Gate 0:** Scope lock, dry-run-first design, AC, CUJs, and Change Ledger complete.
- [x] **Gate 1:** Existing Document/retention/category/control/campaign stacks reused; no second document stack.
- [ ] **Gate 2:** CI green (unit, lint, type, build).
- [ ] **Gate 3:** Staging preview verification and evidence linked.
- [ ] **Gate 4:** Canary execution evidence, if hard disposal is authorised; otherwise N/A with flag false.
- [x] **Gate 5:** Rollback, observability, flag, and evidence-pack plan documented.
