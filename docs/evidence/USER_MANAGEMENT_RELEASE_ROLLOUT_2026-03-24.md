# User Management Release Rollout

Date: 2026-03-24  
Owner: Platform Engineering

## Scope

This rollout covers:

- Microsoft SSO user provisioning and identity linking
- Superuser-only admin user management at `/admin/users`
- Role assignment, activation/deactivation, and last-superuser protection
- Rollout kill switch: `admin_user_management`

## Candidate Build

- Backend auth and user-management changes are included in the candidate SHA
- Frontend admin user-management UI is included in the candidate SHA
- GitHub governance enforcement is included in the candidate SHA

## Pre-Staging Gates

- CI must pass on the candidate SHA
- Frontend build must pass
- Auth and user-management release-focused tests must pass
- No unresolved lint errors on changed files

## Staging Validation

1. Confirm staging deploy completed successfully using the existing deploy workflow.
2. Verify database migrations reached Alembic head.
3. Confirm `/healthz`, `/readyz`, and `/api/v1/meta/version` are healthy.
4. Sign in with Microsoft using an existing linked user.
5. Sign in with Microsoft using a pre-provisioned user with no local password.
6. Confirm a true superuser can open `/admin/users`.
7. Confirm a non-superuser cannot access `/admin/users`.
8. Create a new Microsoft SSO user from `/admin/users`.
9. Edit roles for an existing user from `/admin/users`.
10. Deactivate a non-critical user and verify login is blocked.
11. Attempt to deactivate or demote the last active superuser and verify the operation is blocked.
12. Confirm the kill switch path works:
    - disable `admin_user_management`
    - verify `/admin/users` is hidden/redirected in the frontend
    - verify backend user-management endpoints return unavailable/not found for the feature surface
    - re-enable `admin_user_management`

## Production Promotion Gates

- Staging validation checklist completed
- UAT sign-off recorded
- CAB / governance sign-off recorded if required by release policy
- Production deploy uses the same validated SHA
- Rollback owner identified before promotion

## Production Validation

1. Verify production deploy references the intended SHA.
2. Re-run Microsoft SSO login for a known superuser.
3. Confirm `/admin/users` loads for the superuser.
4. Confirm a non-superuser remains blocked from `/admin/users`.
5. Create one controlled test user or validate an existing prepared user.
6. Confirm role update and deactivate/reactivate flows work.
7. Confirm no auth regressions on refresh-token flow.
8. Monitor auth errors, 401/403 rates, and user-management API failures during the first bake window.

## Kill Switch / Rollback

Primary release control:

- Feature flag key: `admin_user_management`

Immediate mitigation:

1. Disable `admin_user_management`
2. Verify frontend no longer exposes `/admin/users`
3. Verify backend user-management routes are effectively unavailable for the feature surface

If broader rollback is required:

1. Use the documented production rollback workflow / slot swap process
2. Re-verify `/healthz`, `/readyz`, and `/api/v1/meta/version`
3. Re-test Microsoft SSO login after rollback

## Evidence To Attach To PR / Release

- CI run URL
- Staging deployment URL and evidence artifact
- Final release SHA
- Staging validation checklist results
- Production validation notes
- Rollback owner and decision log
