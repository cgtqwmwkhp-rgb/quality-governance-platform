# Change Ledger (CL-PARTNER-SCOPES-DOCS-SEARCH)

## 1) Summary
- **Feature / Change name:** Partner API scopes for CRM Bid Writer (K4) — `documents:read` / `search:read` (+ `policies:read` allowlist)
- **User goal (1–2 lines):** Let a scoped QGP partner bearer call search + document read/signed-url APIs so CRM Bid Writer can federate governance evidence, without opening JWT-only routes to partner tokens.
- **In scope:** Extend `PARTNER_API_SCOPES`; partner authenticate + fail-closed dual-auth deps; gate listed search/document routes; docs; unit tests for allowlist + scope gates
- **Out of scope:** Graph materialise (K4c); CRM flag enablement; narrowing global search hits to documents-only; wiring `policies:read` onto policy routes; webhook emitter work; PRs #1620–#1624
- **Feature flag / kill switch:** None — additive allowlist + opt-in route gates (existing tokens without new scopes unchanged)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `PartnerAuthService.authenticate`; `PartnerPrincipal`; dual-auth deps in `src/api/dependencies/partner.py`; JWT `get_current_user` rejects `qgp_pt_`
- **APIs (endpoints changed/added):**
  - `GET /api/v1/search/` (+ `POST /interpret`) — partner needs `search:read`
  - `GET /api/v1/documents/search/semantic` — partner needs `documents:read`
  - `GET /api/v1/documents/search/content` — partner needs `documents:read`
  - `GET /api/v1/documents/{id}` + `.../signed-url` — partner needs `documents:read`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Partner create schema inherits expanded `PARTNER_API_SCOPES` allowlist
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Docs:** `docs/api/partner-openapi.md`, `docs/ops/partner-webhooks.md`
- **Tests:** `tests/unit/test_partner_api_tokens.py`, `tests/unit/test_partner_bearer_scopes.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive scopes + opt-in partner gates; JWT authz unchanged
- **Tolerant reader / strict writer applied?** Yes — unknown scopes rejected at token create; partner tokens fail closed on JWT-only deps
- **Breaking changes:** None for existing tokens. Presenting a `qgp_pt_` token on a non-gated route now returns a clear `401` (previously JWT decode failure)
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit only

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Partner scope allowlist | `webhooks:manage`, `inspections:read` only | + `documents:read`, `search:read`, `policies:read` |
| Inbound partner bearer | Documented as future; `qgp_pt_` not accepted on app routes | Fail-closed dual-auth on opt-in search/document routes |
| Search / document partner access | N/A | Scope-gated; JWT posture preserved |
| Cross-route partner blast radius | N/A | JWT-only deps reject partner tokens |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `PARTNER_API_SCOPES` includes `documents:read`, `search:read`, `policies:read` (existing scopes retained)
- [x] AC-02: Partner bearer with correct scopes can authenticate on gated search/document routes; missing scope → `403`
- [x] AC-03: Partner bearer on JWT-only routes → `401` (fail-closed)
- [x] AC-04: JWT callers on gated routes keep prior authz (`document:read` / authenticated-only)
- [x] AC-05: Docs list scopes + gated routes; unit tests cover allowlist + gates

## 5) Testing Evidence (link to runs)
- [x] Lint — local import smoke
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `pytest tests/unit/test_partner_api_tokens.py tests/unit/test_partner_bearer_scopes.py` (18 passed locally)
- [ ] Integration tests — CI
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create token with `documents:read` + `search:read` accepted by allowlist
- [x] CUJ-02: Partner with `search:read` passes search gate; without → 403
- [x] CUJ-03: Partner with `documents:read` passes document search gate + maps to `document:read` permission; without → 403
- [x] CUJ-04: Partner token rejected on JWT-only dependency

## 7) Observability & Ops
- **Logs:** Partner `last_used_at` updated on successful authenticate
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** `docs/ops/partner-webhooks.md`, `docs/api/partner-openapi.md`

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Issue staging partner token (see below); call gated routes with/without scopes; confirm JWT session still works
- **Canary plan:** N/A — additive auth surface; no flag
- **Prod post-deploy checks:** Health unchanged; create/revoke partner token smoke; confirm ungated route still rejects `qgp_pt_`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected 401/403 for JWT clients on gated routes, or partner auth incident
- **Rollback steps:** Revert PR / redeploy previous image
- **Owner:** Platform / K4 track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A until merge
- Canary evidence: N/A

---

# Staging token issuance notes (K4 / CRM Bid Writer)

After this lands on staging:

1. As a tenant admin JWT with `admin:manage`:
   ```http
   POST /api/v1/partner-auth/tokens
   Authorization: Bearer <admin_session_jwt>
   Content-Type: application/json

   {
     "name": "CRM Bid Writer K4 (staging)",
     "scopes": ["documents:read", "search:read"]
   }
   ```
2. Store the one-time `token` (`qgp_pt_…`) as staging secret `QGP_PARTNER_TOKEN` for the CRM app.
3. Smoke:
   - `GET /api/v1/search/?q=test` with the partner token → 200
   - Same call with a token that only has `webhooks:manage` → 403
   - `GET /api/v1/documents/search/content?q=test` with partner token → 200/empty (not 401/403)
   - `GET /api/v1/partner-webhooks/events` with partner token → 401 (JWT-only)
4. Do **not** grant `policies:read` until policy routes are wired.

**Residual risk:** `search:read` currently unlocks tenant-wide global search entity hits (incidents, etc.), not documents-only. Follow-up to narrow partner search results is listed under Future in the ops runbook.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive partner scopes + opt-in gates)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — rollback = revert; staging token notes above
