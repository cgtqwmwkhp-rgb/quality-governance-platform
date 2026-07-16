# Change Ledger (CL-GT-FIXNOW-INTEGRITY)

## File allowlist (exclusive)

- `frontend/src/components/ReportChat.tsx`
- `scripts/governance/pr_body_gt_fixnow_integrity.md`
- `src/api/routes/auth.py`
- `src/api/routes/evidence_assets.py`
- `src/core/config.py`
- `src/domain/services/audit_service.py`
- `src/domain/services/evidence_service.py`
- `tests/unit/test_audit_capa_closure_bridge.py`
- `tests/unit/test_auth_role_claims.py`

## 1) Summary

- **Feature / Change name:** fix(gt) — FIX-NOW Golden-Thread UAT integrity residuals
- **User goal:** Stop production local-password JWT issuance by default; remove simulated portal chat delivery; preserve evidence checksums on the primary upload paths; and reject finding/CAPA lifecycle writes that would create a known desynchronisation.
- **In scope:** R90, R70, R65, and R43 only.
- **Out of scope:** Database NOT NULL migration for historical alternate evidence writers; a durable portal-messaging API; and remediation of pre-existing records outside a lifecycle write.

## 2) Impact Map

| Surface | Before | After |
|---|---|---|
| Local `/auth/login` | Issued local-password JWTs in production | Returns 403 unless `ALLOW_LOCAL_PASSWORD_LOGIN=true`; Azure AD exchange remains available |
| Portal ReportChat | Created a local message and claimed delivery | Read-only persisted-message view with an explicit unavailable notice |
| Primary evidence upload | Checksum stored in DB only | SHA-256 is computed and persisted, and also sent with immutable storage metadata |
| Finding/CAPA lifecycle | Some status writes could preserve a desynced chain | Writes producing `desynced_*` chain statuses fail closed; no-op sibling blockers remain safe |

## 3) Compatibility & Data Safety

- Migrations: none.
- Existing alternate evidence writers remain compatible because `evidence_assets.checksum_sha256` remains nullable.
- Break-glass local login requires an explicit, auditable production environment setting: `ALLOW_LOCAL_PASSWORD_LOGIN=true`.
- Rollback: revert this PR. No schema or data rollback is required.

## 4) Acceptance Criteria

- [x] AC-01 (R90): Local password login is disabled when `APP_ENV=production` or `ENVIRONMENT=production`, unless `ALLOW_LOCAL_PASSWORD_LOGIN=true`.
- [x] AC-02 (R70): ReportChat cannot simulate message creation, attachment upload, or delivery.
- [x] AC-03 (R65): Both primary evidence upload implementations calculate SHA-256 and include it in persisted storage metadata.
- [x] AC-04 (R43): Finding status writes and CAPA bridge writes reject a resulting `desynced_*` chain state.

## 5) Testing Evidence

- `pytest tests/unit/test_auth_role_claims.py tests/unit/test_audit_capa_closure_bridge.py` — 22 passed.
- `cd frontend && npm run build && npm run lint` — passed.
- `git diff --check` — passed.

## 6) Critical Journeys

- [x] CUJ-01: Production local-password login is denied by default and explicitly enabled only for break-glass.
- [x] CUJ-02: A CAPA reaching verification/closed updates a finding only when the resulting chain remains aligned.
- [x] CUJ-03: Evidence upload calculates SHA-256 before blob upload and retains it with evidence metadata.

## 7) Observability

- Blocked production local-password login emits a warning without credentials.
- The portal clearly states that messaging is unavailable instead of rendering false delivery status.
- Lifecycle errors include the truthful `desynced_*` status name.

## 8) Release Plan

- Squash-merge only after review and required CI checks pass.
- Confirm production environment has `ALLOW_LOCAL_PASSWORD_LOGIN` unset or false.
- Verify Azure AD token exchange and one evidence upload after deployment.

## 9) Rollback Plan

- **Rollback steps:** Revert the squash merge; no migration downgrade or data rollback is required.
- **Owner:** Platform / QGP conveyor.

## 10) Evidence Pack

- This Change Ledger.
- Focused authentication and audit-bridge test output.
- Golden-Thread UAT residual references: R90, R70, R65, R43.

---

# Gate Checklist

- [x] **Gate 0:** Scope, acceptance criteria, and rollback documented.
- [x] **Gate 1:** Touched backend unit tests and whitespace validation pass.
- [x] **Gate 2:** Frontend build and lint passed locally.
- [ ] **Gate 3:** CI checks pending PR.
- [ ] **Gate 4:** tip==LIVE deployment verification pending merge.
- [ ] **Gate 5:** Production UAT residual retest pending deployment.
