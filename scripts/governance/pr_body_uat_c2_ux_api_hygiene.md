# Change Ledger (CL-UAT-C2-UX-API)

## Summary

- **Feature / Change name:** Wave C2 UAT API/UX hygiene — near-miss validation, campaign list + evidence PDF honesty
- **User goal:** Close highest-value remaining UAT API failures without UI redesign; return honest 422/200 instead of silent accept / 500 / missing-query 422
- **In scope:** ACT-027 NM validation; ACT-044 evidence-pack.pdf 500; ACT-045 campaigns global list; ACT-023 near-miss trailing-slash alias; PX-039/040/027 shared date validation; incident future-date guard (shared validator); unit tests; OpenAPI regen
- **Out of scope:** LIBRARY_DISPOSAL_EXECUTE; Alembic-on-App-Service-startup; ACT-042 PAMS integration (tip already structured 503); PX-003…058 UI polish (Wave C2b/D); partner-webhooks FE `/api/v1` prefix (PX-010 — separate FE PR)

## Impact Map

| ID | Surface | Before | After |
|---|---|---|---|
| ACT-027 | `PATCH /api/v1/near-misses/{id}` | Soft accept invalid `potential_severity`; empty PATCH no-op | Pattern + min_length validators → 422; empty body rejected |
| PX-039 | `POST /api/v1/near-misses/` | Accepted `event_date` 2099 (201) | Shared `reject_future_statutory_datetime` → 422 |
| PX-040 | NM create/PATCH | Silent/soft invalid payloads | Create requires fields (existing); PATCH empty → 422 |
| ACT-044 | `GET …/campaigns/{id}/evidence-pack.pdf` | 500 when roster empty (fpdf2 `bytearray` + StreamingResponse) | Returns valid PDF bytes (header-only pack) → 200 |
| ACT-045 | `GET /api/v1/document-campaigns/campaigns?page=&page_size=` | 422 (required `document_id`) | Global tenant list 200; optional `document_id` filter retained |
| ACT-023 | `GET/POST /api/v1/near-misses` (no slash) | 404 | Dual-mount alias → same contract as trailing-slash routes |
| Incident | `POST/PATCH /incidents` future dates | Accepted | Same shared future-date guard → 422 |
| ACT-042 | Vehicle checklists | — | **Residual** — tip returns structured 503 when PAMS unavailable |

## Compatibility

- `GET /document-campaigns/campaigns`: `document_id` changes required → optional; adds `page` / `page_size` (defaults preserve prior behaviour when filter supplied)
- Near-miss PATCH: invalid enum/severity values now 422 (previously persisted or silently ignored)
- Near-miss/incident future statutory dates now 422 (previously accepted)
- No new env flags; `LIBRARY_DISPOSAL_EXECUTE` not enabled
- No Alembic revisions; no App Service startup migration hook

## Acceptance Criteria

- [x] AC-01: `POST /near-misses/` with future `event_date` → 422
- [x] AC-02: `PATCH /near-misses/{id}` with invalid `potential_severity` or `{}` → 422
- [x] AC-03: `GET /document-campaigns/campaigns?page=1&page_size=10` (no `document_id`) → 200 `{items,total}`
- [x] AC-04: `GET …/evidence-pack.pdf` with empty roster → 200 PDF bytes (not 500)
- [x] AC-05: `GET /near-misses` without trailing slash → 200 list contract
- [x] AC-06: Unit suite `tests/unit/test_wave_c2_uat_api_hygiene.py` green
- [ ] AC-07: CI gates (black/isort/mypy/openapi) green on PR
- [ ] AC-08: tip LIVE smoke after merge — prod UAT re-run for covered ACT IDs

## Testing Evidence

- [x] `pytest tests/unit/test_wave_c2_uat_api_hygiene.py -q` — 7 passed
- [x] `pytest tests/unit/test_document_campaign_service.py::TestBuildEvidencePackPdf -q` — regression green
- [x] `mypy` on touched route/schema/service modules — clean
- [x] OpenAPI baseline + `docs/contracts/openapi.json` regenerated
- [ ] Full CI on PR

## Critical Journeys

- [x] CUJ-01: HSEQ campaigns inbox list loads without `document_id` query param
- [x] CUJ-02: Campaign evidence PDF export succeeds for draft/empty-roster campaigns
- [x] CUJ-03: Near-miss API rejects absurd future event dates (compliance record integrity)
- [x] CUJ-04: Near-miss PATCH returns validation errors for bad severity / empty body
- [x] CUJ-05: Staff near-miss list/create without trailing slash resolves (no 404)
- [ ] CUJ-06: tip LIVE prod verification post-merge

## Observability

- Monitor 5xx drop on `/document-campaigns/campaigns/*/evidence-pack.pdf`
- Monitor 422 rate increase on `/near-misses` create/patch (expected honesty, not errors)
- Log keys unchanged; no new PII in logs

## Release Plan

1. Merge PR after CI + review (do **not** merge from authoring agent)
2. Deploy API tip to prod (standard conveyor — no Alembic-on-startup)
3. Re-run UAT Wave C2 probes for ACT-027/044/045/023

## Rollback Plan

- **Owner:** Platform / on-call release manager
- **Trigger:** Regression on campaigns list, evidence PDF export, or near-miss CRUD
- **Steps:** Revert squash-merge commit; redeploy previous prod tip (`aa8cfc5d`)

## Evidence Pack

- Unit: `tests/unit/test_wave_c2_uat_api_hygiene.py`
- OpenAPI: `openapi-baseline.json`, `docs/contracts/openapi.json`
- This ledger: `scripts/governance/pr_body_uat_c2_ux_api_hygiene.md`

---

# Gate Checklist

- [x] **Gate 0:** Scope, Change Ledger, AC, rollback reviewed; LIBRARY_DISPOSAL_EXECUTE off; no Alembic-on-startup
- [ ] **Gate 1:** black / isort / mypy / OpenAPI CI green
- [x] **Gate 2:** Focused unit suites green locally
- [ ] **Gate 3:** tip LIVE UAT re-probe after merge
- [x] **Gate 4:** No canary required — validation + read-path hardening only
- [ ] **Gate 5:** Prod evidence attached post-deploy
