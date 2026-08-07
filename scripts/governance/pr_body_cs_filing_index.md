# Change Ledger (CL-CS-FILING-INDEX-ON-FILE)

## 1) Summary
- **Feature / Change name:** Index/chunk on Compliance Schedule File-to-Library (pipeline slice 2)
- **User goal (1–2 lines):** When an operator files occurrence or FRA OCR evidence into the Governance Library, the filed DRAFT is chunked/indexed for Library search — without silently approving it.
- **In scope:** Occurrence filing + FRA OCR draft filing IndexJob creation; hard-OCR status fix for `category_id` docs; flag + deploy persistence; response `index_job_id`
- **Out of scope:** Slices 3–6 (eligibility field, from-evidence OCR, CAPA/Risk); Doc Graph; PDF inline preview; FE UI
- **Feature flag / kill switch:** `COMPLIANCE_FILING_INDEX_ENABLED` / `compliance_filing_index_enabled` — **default OFF**. Persist across deploys via `vars.*` (same pattern as FRA OCR #1629).

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** `compliance_schedule_filing_service.py`, `compliance_schedule_fra_ocr_service.py`, `index_job_service.py` (helpers + hard-OCR lifecycle fix)
- **APIs:** Filing responses optionally include `index_job_id`; routes dispatch after commit
- **Database:** None (reuses `index_jobs` / `document_chunks`)
- **Config/env/flags:** `COMPLIANCE_FILING_INDEX_ENABLED` in config, deploy-staging/production, `scripts/infra/env-vars.json`
- **Dependencies:** None
- **Tests:** `tests/unit/test_compliance_filing_index_on_file.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive optional response field; behaviour gated off by default
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — set flag false / revert deploy; no schema change

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Filed CS evidence searchable | Document DRAFT only; no IndexJob | With flag on: IndexJob + chunks; status remains DRAFT |
| Governance lifecycle on index | Hard OCR set filed docs to FAILED | `category_id` docs keep DRAFT + `indexing_error` |
| Pinecone / OCR cost control | N/A | Flag default off; deploy-persisted |
| Link-existing filing | N/A | Still no IndexJob (existing doc unchanged) |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** With flag OFF, File-to-Library creates Document DRAFT and no IndexJob (current behaviour).
- [x] **AC-02:** With flag ON, occurrence file mode creates exactly one pending IndexJob in the same commit as the Document.
- [x] **AC-03:** With flag ON, FRA OCR draft file creates exactly one IndexJob; routes dispatch after commit (Celery, sync fallback).
- [x] **AC-04:** After successful index of a filed (`category_id`) document, status remains DRAFT (not INDEXED/APPROVED).
- [x] **AC-05:** Hard OCR failure on `category_id` document leaves DRAFT with `indexing_error` set (not FAILED).
- [x] **AC-06:** Link-existing mode never creates an IndexJob even when flag is on.
- [x] **AC-07:** Deploy workflows + env-vars registry persist `COMPLIANCE_FILING_INDEX_ENABLED` (default false if unset).

## 5) Testing Evidence
- [x] Unit — `test_compliance_filing_index_on_file.py` (flag gate, one job, link skip, DRAFT after success, DRAFT on hard OCR, non-category still FAILED)
- [x] Existing filing / FRA OCR / library index unit suites remain green
- [ ] Lint / typecheck / CI — after PR open

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Flag off → File occurrence evidence to Library → DRAFT document, no index job, Library search unchanged for that doc.
- [x] **CUJ-02:** Flag on → File occurrence PDF → IndexJob dispatched → chunks present → searchable; document still DRAFT awaiting review/approve.
- [x] **CUJ-03:** Flag on → Confirm FRA OCR draft → File to Library → same index path; status DRAFT.

## 7) Observability & Ops
- **Logs:** Existing index job / Celery dispatch warnings; filing audit payload includes `index_job_id` when present
- **Runbook:** Flip via `gh variable set COMPLIANCE_FILING_INDEX_ENABLED --body true|false` and/or merge-only `az webapp config appsettings set` (never full PUT). Worker/beat receive the same var on deploy.

## 8) Release Plan
- Squash-merge to `main` → Main CI → Azure deploy → verify ACA/app image tip SHA + health.
- Bake: leave flag **false** in prod until operator opts in on a low-volume tenant.

## 9) Rollback Plan
- **Trigger:** Unexpected index load, FAILED drafts, or search pollution
- **Rollback owner:** Platform / on-call engineer (sole operator: David Harris)
- **Steps:**
  1. `gh variable set COMPLIANCE_FILING_INDEX_ENABLED --body false --repo cgtqwmwkhp-rgb/quality-governance-platform`
  2. `az webapp config appsettings set -g <rg> -n <app> --settings COMPLIANCE_FILING_INDEX_ENABLED=false` (merge-only; never full PUT) for API + worker/beat if needed
  3. Revert squash commit on main if code fix required; redeploy prior tip

## 10) Evidence Pack
- CI / staging / prod tip: linked after merge and LIVE verify

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (slice 2 only)
- [x] **Gate 1:** Contracts (optional `index_job_id`; flag default off)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — flag off)
- [x] **Gate 5:** Rollback via var/appsetting documented
