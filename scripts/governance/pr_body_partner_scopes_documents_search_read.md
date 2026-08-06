# Change Ledger (CL-PARTNER-SCOPES-DOCS-SEARCH)

## 1) Summary
- **Feature / Change name:** Partner API scopes for CRM Bid Writer (K4) — `documents:read` / `search:read` (+ `policies:read` allowlist)
- **User goal (1–2 lines):** Let a scoped QGP partner bearer call search + document read/signed-url APIs so CRM Bid Writer can federate governance evidence, without opening any other route to partner tokens.
- **In scope:** Extend `PARTNER_API_SCOPES`; inbound partner bearer authentication; per-route opt-in gate on five GET routes; restrict partner global search to document modules; docs; unit tests
- **Out of scope:** Graph materialise (K4c); CRM flag enablement; wiring `policies:read` onto policy routes; webhook emitter work; PRs #1620–#1624
- **Feature flag / kill switch:** None — additive allowlist plus per-route opt-in (existing tokens and all JWT callers unchanged)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `PartnerAuthService.authenticate` / `touch_last_used`; `PartnerPrincipal`; `src/api/dependencies/partner.py` (route opt-in marker + principal resolution); `get_current_user` resolves `qgp_pt_` bearers on opted-in routes only; `SearchService.search` gains an `allowed_modules` allowlist
- **APIs (endpoints changed/added):** No new endpoints, no changed request/response shapes. Five existing GET routes additionally accept a partner bearer:
  - `GET /api/v1/search/` — `search:read`
  - `GET /api/v1/documents/search/semantic` — `documents:read`
  - `GET /api/v1/documents/search/content` — `documents:read`
  - `GET /api/v1/documents/{id}` — `documents:read`
  - `GET /api/v1/documents/{id}/signed-url` — `documents:read`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Partner create schema inherits the expanded `PARTNER_API_SCOPES`. Each opted-in operation publishes `x-qgp-partner-scope`, so the gate is visible in the OpenAPI document rather than only in Python.
- **Database (migrations/entities/indexes):** None. Scopes are a Python allowlist over an existing JSONB column.
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Docs:** `docs/api/partner-openapi.md` (scopes, gated routes, failure modes, reach, audit trail, staging issuance runbook), `docs/ops/partner-webhooks.md`
- **Tests:** `tests/unit/test_partner_bearer_scopes.py` (25), `tests/unit/test_partner_api_tokens.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** The JWT path in `get_current_user` is untouched. The partner branch is guarded on the `qgp_pt_` prefix, and such a string could only ever 401 before this change because `decode_token` cannot read one — so the set of requests whose behaviour changes is exactly "partner bearer on an opted-in route".
- **Tolerant reader / strict writer applied?** Yes — unknown scopes rejected at token create; unreadable route metadata resolves to "no partner access".
- **Breaking changes:** None. No route lost a dependency, no handler signature changed, and `tests/unit/test_semantic_search_permission.py` still passes as written — that was the constraint the design was built around.
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit only

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Partner scope allowlist | `webhooks:manage`, `inspections:read` | + `documents:read`, `search:read`, `policies:read` |
| Inbound partner bearer | Documented as future; `qgp_pt_` accepted nowhere | Accepted on five GET routes that opt in by name; refused everywhere else |
| Default posture for a partner token | N/A | Deny. Reachability is decided by the route's opt-in, not by the token's scopes |
| Partner tenant isolation | N/A | Tenant bound from the token row (never from request input); same RLS GUC as a session user |
| Partner privilege ceiling | N/A | `is_superuser` always false; only `documents:read` → `document:read` is granted, so `all_staff` library documents only |
| Partner reach in global search | N/A | `Documents` / `Document Content` only — the confidential registers are not queried at all |
| Partner attribution in audit trail | N/A | `user_id` NULL, `user_name` = `Partner: <token name>` |
| JWT session authz | `document:read` where required; authenticated-only elsewhere | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `PARTNER_API_SCOPES` includes `documents:read`, `search:read`, `policies:read`; existing scopes retained
- [x] AC-02: Partner bearer with the route's scope is served on all five routes; genuine token without it → `403`
- [x] AC-03: Partner bearer on any route that did not opt in → `401`, including `GET /api/v1/documents/` which checks the same `document:read` the scope maps to
- [x] AC-04: Unknown, malformed and revoked partner tokens → `401`, and never reach the billed vector store
- [x] AC-05: JWT callers on the five routes keep prior authz — proven by `test_semantic_search_permission.py` passing unmodified
- [x] AC-06: Partner tenant scope is taken from the token row; the vector filter is pinned to it
- [x] AC-07: Partner global search does not query incidents, near misses, RTAs, complaints, risks, audits, actions or compliance
- [x] AC-08: The exact set of partner-callable routes is pinned by a test, so a sixth cannot be added silently

## 5) Testing Evidence (link to runs)
- [x] Lint — `black --check` and `flake8` clean on all changed files
- [x] Typecheck — `scripts/validate_type_ignores.py` passes; no new ignores in `src/`
- [x] Build — `src.main` imports and mounts; `scripts/validate_openapi_contract.py` passes (767 paths)
- [x] Unit tests — full `tests/unit`: **5484 passed, 4 failed, 10 skipped**. The 4 failures are `test_gemini_ai_upstream_breaker.py` / `test_gemini_review_upstream_breaker.py` and were verified to fail identically with this change stashed (pre-existing, unrelated to partner auth).
- [x] Authorisation governance — `tests/integration/test_route_authorisation_census.py`, `test_permission_catalogue.py`, `test_permission_route_walk.py`, `test_route_census_classification.py`, `test_route_authz_tenant_scope.py`: 97 passed. No route posture changed and `AUTHENTICATED_ONLY_DEBT` is untouched.
- [x] Import boundaries — `scripts/check_import_boundaries.py` OK
- [ ] Integration tests (DB-backed) — CI
- [ ] E2E Smoke (critical journeys) — CI

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create token with `documents:read` + `search:read` accepted by the allowlist
- [x] CUJ-02: Partner with `documents:read` is served `GET /documents/search/semantic`; the same token is refused `401` on `GET /documents/`
- [x] CUJ-03: Partner with only `search:read` gets `403` on document search, and reaches no confidential register through global search
- [x] CUJ-04: Revoked token (`is_active` false, secret still valid) → `401`
- [x] CUJ-05: Session user with `document:read` unaffected on every gated route

## 7) Observability & Ops
- **Logs:** Partner activity is attributable in `library_document_access_logs` / `document_search_logs` via `user_name = Partner: <token name>` with a NULL `user_id`
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** `docs/api/partner-openapi.md` (staging issuance + verification), `docs/ops/partner-webhooks.md`
- **Known limitation:** `last_used_at` is advanced in the request's own transaction, so it does not advance on a request that never commits. It is credential-hygiene telemetry and is not an authorisation input.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Issue the CRM token (runbook below); confirm `200` on the gated routes, `401` on `GET /api/v1/documents/`, and that a session user is unaffected
- **Canary plan:** N/A — additive, opt-in auth surface
- **Prod post-deploy checks:** Health unchanged; create/revoke partner token smoke; confirm an ungated route still rejects `qgp_pt_`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any unexpected 401/403 for JWT clients, or a partner auth incident
- **Rollback steps:** Revert PR / redeploy previous image. No data migration to unwind.
- **Owner:** Platform / K4 track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A until merge
- Canary evidence: N/A

---

# Design note: why the gate is a route opt-in

The first attempt at this replaced the identity dependency on each partner-callable
route with a `require_permission_or_partner_scope(...)` factory. That is the wrong
shape, and it failed concretely rather than aesthetically:

- It removed `get_current_user` from those routes' dependency graphs, so every test
  that overrides it stopped applying — five behavioural assertions in
  `tests/unit/test_semantic_search_permission.py` went red, and a valid session
  user got `401` on `GET /documents/search/semantic`.
- It removed the literal `require_permission("document:read")` those routes are
  pinned on, breaking two static guardrails in the same file.
- It reached `has_permission` with a non-literal token, which
  `src/domain/authz/extraction.py` refuses outright — `scan_source_tree()` raised
  `UndeclaredDynamicSiteError`, which breaks the permission catalogue for the whole
  repository, not just for these routes.

So partner identity is resolved inside the one existing identity dependency, and
reachability is a separate, declarative decision carried on the route:

```python
@router.get("/search/content", openapi_extra=partner_readable("documents:read"))
```

`required_partner_scope` reads that marker back off the matched route. No marker
means no scope, and no scope refuses the token — which is the behaviour that
already existed. The opt-in is read from the route object rather than from a
sibling dependency because dependency *resolution order* is not a contract worth
resting a security decision on, and because a route that cannot be read at all
then denies rather than admits.

Consequences worth stating plainly:

- Every `require_permission` dependency already on these routes still runs and is
  still what decides, for both kinds of caller. Nothing about authorisation was
  reimplemented.
- Route census postures are unchanged, so no authorisation debt declaration or
  ratchet moved.
- `PartnerPrincipal` is not a `User` and is not a subclass of one. It carries only
  the attributes the reachable handlers read, under `__slots__`, so an attribute
  nobody considered raises instead of being answered with a plausible lie.

## Deviation from the brief: partner global search is narrowed

The brief asked for `search:read` on `GET /api/v1/search/` and did not ask for the
results to be narrowed. Shipping it unnarrowed would have handed a long-lived
bearer, stored in another system's configuration, tenant-wide read of incidents,
near misses, RTAs, complaints, risks (C3-confidential), audit findings and actions
— because those modules are scoped by tenant but gated by no permission at all.
A partner caller therefore searches the `Documents` and `Document Content` modules
only, via a new `allowed_modules` allowlist on `SearchService.search` that defaults
to `None` and so is inert for every session caller. Excluded modules are not
queried rather than filtered afterwards.

The superseded revision of this PR body recorded this same exposure as accepted
"residual risk". It is closed here instead.

---

# Staging token issuance (K4 / CRM Bid Writer)

Full runbook, including rotation and revocation, is in
`docs/api/partner-openapi.md` → "Issuing the CRM Bid Writer token (staging)".

1. As a tenant admin holding `admin:manage`, against the staging FQDN, for the
   tenant the CRM instance serves:

   ```http
   POST /api/v1/partner-auth/tokens
   Authorization: Bearer <admin_session_jwt>
   Content-Type: application/json

   {
     "name": "CRM Bid Writer K4 (staging)",
     "scopes": ["documents:read", "search:read"]
   }
   ```

   Grant both scopes: `search:read` alone returns document titles with no chunk
   text.

2. Store the one-time `token` (`qgp_pt_…`) as the staging secret
   `QGP_PARTNER_TOKEN` for the CRM app. Keep the returned `id` (to revoke) and
   `token_prefix` (what appears in `GET /partner-auth/tokens`).

3. Smoke — the `401` matters as much as the `200`, because it is what proves the
   opt-in is doing the deciding:

   - `GET /api/v1/search/?q=test` → `200`
   - `GET /api/v1/documents/search/content?q=test` → `200` (possibly empty)
   - `GET /api/v1/documents/` → `401` (did not opt in)
   - `GET /api/v1/partner-webhooks/events` → `401` (did not opt in)
   - A token holding only `webhooks:manage` on any of the above → `401`/`403`
   - A tenant admin session JWT on the same routes → unchanged

4. Do **not** grant `policies:read`. It is allowlisted so a token can be minted
   ahead of a policy surface, and it currently grants no permission and opens no
   route.

5. To rotate: mint the replacement, deploy it to CRM, then `DELETE` the old `id`.
   Revocation takes effect on the next request — `is_active` is checked per call
   and never cached.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive partner scopes + per-route opt-in)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — rollback = revert; staging runbook above
