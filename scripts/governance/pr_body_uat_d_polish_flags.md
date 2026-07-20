# Change Ledger (CL-UAT-D-POLISH-FLAGS)

## Summary

- **Feature / Change name:** Wave D UAT polish/flags — AI health auth, engineer dual-gate clarity, signatures dead-end CTA
- **User goal:** Close quick, safe P3 UAT leftovers without product decisions or risky flag changes
- **In scope:** ACT-046 `/api/v1/ai/health` auth + redaction; ACT-053 engineer:create dual-gate docs + FE honesty; P3 Digital Signatures disabled New Request CTA + banner; unit tests; OpenAPI regen
- **Out of scope:** LIBRARY_DISPOSAL_EXECUTE (stays off); Alembic-on-App-Service-startup; ACT-032/033 product flags; ACT-030 SWA bake map; ACT-050/051 P1 fixes; granting engineer:create without manager facet

## Impact Map

| ID | Surface | Before | After |
|---|---|---|---|
| ACT-046 | `GET /api/v1/ai/health` | Unauth 200 with hardcoded service flags + `claude_ai` env probe | Auth required (401/403 unauth); configuration-only payload via upstream readiness helpers; no secret leakage |
| ACT-053 | `POST /engineers`, `POST /sync-from-pams` | Dual gate documented only in code comments | Module doc + runbook + FE disables Add/Sync for non-manager roles with honesty banner |
| P3 | `DigitalSignatures.tsx` | Enabled “New Request” opens dead-end modal with misleading Create button | Disabled CTA + coming-soon honesty banner; modal footer is cancel-only |
| Residual | ACT-030, ACT-031, ACT-032, ACT-033 | — | Documented out of scope (product/hygiene/flags) |
| Residual | ACT-050, ACT-051, ACT-052 | — | P1/P2 — separate remediation waves |

## Compatibility

- `GET /api/v1/ai/health`: breaking for unauthenticated callers — use `/healthz` / `/readyz` for probes; authenticated ops dashboards must send Bearer token
- Engineer roster writes unchanged (still require manager facet + `engineer:create`)
- No new env flags; `LIBRARY_DISPOSAL_EXECUTE` not enabled
- No Alembic revisions; no App Service startup migration hook

## Acceptance Criteria

- [x] AC-01: Unauthenticated `GET /api/v1/ai/health` → 401 or 403
- [x] AC-02: Authenticated `/ai/health` returns configuration honesty payload (no secret substrings, no theatre `services` map)
- [x] AC-03: `docs/runbooks/workforce-engineer-rbac.md` documents engineer:create + manager dual gate
- [x] AC-04: Employees page hides/disables Add + PAMS sync for non-admin/supervisor JWT roles with honesty banner
- [x] AC-05: Digital Signatures “New Request” disabled with coming-soon banner (no dead-end Create CTA)
- [x] AC-06: `pytest tests/unit/test_wave_d_uat_polish.py -q` green
- [ ] AC-07: CI gates (black/isort/mypy/openapi) green on PR
- [ ] AC-08: tip LIVE smoke — unauth `/ai/health` probe returns 401/403 post-deploy

## Testing Evidence

- [x] `pytest tests/unit/test_wave_d_uat_polish.py -q` — 3 passed
- [x] OpenAPI regen + `python3.11 scripts/validate_openapi_contract.py` — pass (693 paths)
- [x] `frontend/src/utils/__tests__/workforceAccess.test.ts` added (CI vitest lane)
- [ ] Full CI on PR

## Critical Journeys

- [x] CUJ-01: Platform ops authenticated session can read `/api/v1/ai/health` configuration meta
- [x] CUJ-02: Internet/unauthenticated probe of `/ai/health` fails closed (no env leakage)
- [x] CUJ-03: Supervisor/admin can still Add employee + Sync from PAMS on Employees page
- [x] CUJ-04: Staff persona sees disabled roster CTAs + dual-gate honesty copy (no 403 surprise)
- [x] CUJ-05: Digital Signatures page no longer invites a dead-end create flow
- [ ] CUJ-06: tip LIVE prod verification post-merge

## Observability

- Monitor 401/403 rate on `/api/v1/ai/health` (expected increase if external scanners hit old unauth probe)
- No new log PII; AI health payload remains configuration flags only

## Release Plan

1. Merge PR after CI + review (do **not** merge from authoring agent)
2. Deploy API + SWA tip via standard conveyor — no Alembic-on-startup
3. Re-run thin UAT probe for ACT-046; confirm ACT-053 UX with staff vs supervisor personas

## Rollback Plan

- **Owner:** Platform / on-call release manager
- **Trigger:** Regression on authenticated AI ops dashboards, workforce roster UX, or signatures page
- **Steps:** Revert squash-merge commit; redeploy previous prod tip (`2b4a26c2`)

## Evidence Pack

- Unit: `tests/unit/test_wave_d_uat_polish.py`
- Runbook: `docs/runbooks/workforce-engineer-rbac.md`
- OpenAPI: `openapi-baseline.json`, `docs/contracts/openapi.json`
- This ledger: `scripts/governance/pr_body_uat_d_polish_flags.md`

---

# Gate Checklist

- [x] **Gate 0:** Scope, Change Ledger, AC, rollback reviewed; LIBRARY_DISPOSAL_EXECUTE off; no Alembic-on-startup
- [ ] **Gate 1:** black / isort / mypy / OpenAPI CI green
- [x] **Gate 2:** Focused unit suite green locally
- [ ] **Gate 3:** tip LIVE UAT re-probe after merge
- [x] **Gate 4:** No canary required — auth hardening + FE honesty only
- [ ] **Gate 5:** Prod evidence attached post-deploy
