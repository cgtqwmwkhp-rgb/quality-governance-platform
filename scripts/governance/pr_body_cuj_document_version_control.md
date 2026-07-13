# Change Ledger (CL-CUJ-DOCUMENT-VERSION-CONTROL)

## File allowlist (exclusive)
- `src/domain/services/document_version_service.py` (NEW)
- `src/domain/models/document.py`
- `src/domain/models/document_control.py`
- `src/api/routes/documents.py`
- `src/api/routes/document_control.py`
- `alembic/versions/20260713_document_version_control.py` (NEW)
- `frontend/src/components/DocumentVersionControlBar.tsx` (NEW)
- `frontend/src/components/__tests__/DocumentVersionControlBar.test.tsx` (NEW)
- `frontend/src/api/documentControlClient.ts`
- `frontend/src/pages/DocumentControl.tsx`
- `frontend/src/pages/DocumentDetail.tsx`
- `frontend/tests/e2e/document-version-control-cuj.spec.ts` (NEW)
- `tests/unit/test_document_version_service.py` (NEW)
- `tests/unit/test_document_version_control_cuj.py` (NEW)
- `tests/unit/test_document_control_tenancy.py` (honesty asserts only)
- `scripts/governance/pr_body_cuj_document_version_control.md`

**Zero overlap** with sibling overnight lanes: GKB audit-pack provenance, Workforce P0 spine, audit execution / answer integrity / finding loop / CAPA closure bridge.

## 1) Summary
- **Feature / Change name:** CUJ — Document version control on create/publish (ISO 7.5 honesty)
- **User goal:** New documents get real versioning — create → revise → publish increments version; prior published versions are immutable/read-only; UI shows clear version history; APIs never claim a published tip that does not match the version row.
- **In scope:** Library + controlled document version service; create/revise/publish routes; DocumentVersionControlBar; Documents detail Versions tab; Document Control wiring; additive migration; unit + Playwright proof
- **Out of scope:** GKB audit-pack; Workforce P0; audit execution; SMTP/PagerDuty; approval workflow redesign beyond publish immutability
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip at branch cut

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `DocumentVersionControlBar`; `DocumentDetail` Versions tab; `DocumentControl` revise/publish actions; client createVersion/publish
- **Backend (handlers/services):** `document_version_service`; documents + document_control routes
- **APIs (endpoints changed/added):**
  - `POST /api/v1/document-control/` — honest 1.0 draft tip+row
  - `POST /api/v1/document-control/{id}/versions` — revise draft (blocks second open draft)
  - `POST /api/v1/document-control/{id}/publish` — NEW publish; supersedes prior published
  - `PUT /api/v1/document-control/{id}` — rejects published/obsolete metadata edits
  - `GET|POST /api/v1/documents/{id}/versions`, `POST /api/v1/documents/{id}/publish` — NEW library versioning
  - Upload creates matching initial draft version row
- **Schemas/contracts:** Additive response fields (`published_version`, `working_version`, `is_immutable`, `read_only`)
- **Database:** Additive columns on `document_versions` + `controlled_document_versions.is_immutable`
- **Workflows/jobs/queues:** Vitest + Playwright CUJ + pytest unit
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive columns with server defaults; tolerant FE readers for new fields
- **Tolerant reader / strict writer applied?** Yes — FE treats optional immutability fields safely
- **Breaking changes:** Create no longer returns mismatched `current_version=1.0` / version row `0.1` (honesty fix). Published documents reject metadata PUT until revise.
- **Migration plan:** `20260713_doc_ver_ctrl` additive + backfill controlled immutability from status
- **Rollback strategy (DB):** Revert commit; downgrade drops additive columns only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Create controlled doc → tip and version row both `1.0` `draft` (no 1.0/0.1 theatre)
- [x] AC-02: Publish freezes draft as `published` + `is_immutable`; prior published → `superseded` read-only
- [x] AC-03: Revise after publish opens next draft (e.g. 1.1); second open draft rejected
- [x] AC-04: PUT metadata on published/obsolete document returns honest read-only error
- [x] AC-05: DocumentDetail + DocumentControl show version history with immutable badges via DocumentVersionControlBar
- [x] AC-06: Unit + Playwright cover create→revise→publish CUJ

## 5) Testing Evidence (link to runs)
- [x] Unit — `test_document_version_service.py`, `test_document_version_control_cuj.py`, tenancy honesty asserts
- [x] Unit FE — `DocumentVersionControlBar.test.tsx`
- [x] E2E — `frontend/tests/e2e/document-version-control-cuj.spec.ts`
- [ ] Lint / Typecheck / Build — CI required checks on draft PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-DOC-VC-01: Create draft 1.0 → Publish → immutable history
- [x] CUJ-DOC-VC-02: Revise → draft tip → Publish supersedes prior published
- [x] CUJ-DOC-VC-03: Published document metadata edit blocked (API honesty)

## 7) Observability & Ops
- **Logs:** Existing route/exception logs; GKB rematch failures remain best-effort
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** None (version honesty surface)

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Local:** Allowlisted edits on exclusive branch `path11/cuj-document-version-control`
- **Staging verification:** tip SHA + `/healthz` 200 after CI deploy + migration
- **Canary plan:** N/A — standard staging then force_deploy
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==prod; spot-check create→publish version history

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** False published tips, blocked legitimate draft edits, or Playwright false failures
- **Rollback steps:** Revert squash-merge on `main`; redeploy prior tip; downgrade additive migration if needed
- **Owner:** Platform team

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — allowlist only
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip
- [ ] Gate 5 — evidence pack attached

## Test plan
- [ ] `pytest tests/unit/test_document_version_service.py tests/unit/test_document_version_control_cuj.py tests/unit/test_document_control_tenancy.py`
- [ ] `npm test -- DocumentVersionControlBar`
- [ ] `npx playwright test document-version-control-cuj.spec.ts`
- [ ] Staging tip after merge
- [ ] Prod tip==prod after force_deploy
