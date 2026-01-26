# UX Coverage Test User Specification

> **Classification**: Operations | Staging Only | Restricted Access
> **Last Updated**: 2026-01-26
> **Owner**: Platform Team

## Purpose

This document defines the test user account used for automated UX functional coverage testing in CI/CD. The test user enables Playwright audits to exercise auth-protected routes and workflows.

## User Specification

### Identity

| Attribute | Value |
|-----------|-------|
| **Email** | `ux-test-runner@staging.local` |
| **Display Name** | UX Coverage Test Runner |
| **Account Type** | Service Account |
| **Environment** | Staging ONLY |

> **PII Policy**: Email stored only in GitHub Secrets. Never appears in logs, artifacts, or screenshots.

### Required Roles

The test user must have the following roles to exercise all P0/P1 routes:

| Role | Purpose | Scope |
|------|---------|-------|
| `user` | Base access for portal pages | Portal routes |
| `employee` | Submit reports via employee portal | Portal workflows |
| `admin` | Access admin dashboard and list views | Admin routes |
| `viewer` | Read incidents, RTAs, complaints | Admin detail pages |

### Permissions Matrix

| Route Category | Auth Type | Access Required | Role |
|----------------|-----------|-----------------|------|
| `/portal/*` | `portal_sso` | Read/Write | `employee` |
| `/dashboard` | `jwt_admin` | Read | `admin` |
| `/incidents/*` | `jwt_admin` | Read/Write | `admin`, `viewer` |
| `/rtas/*` | `jwt_admin` | Read/Write | `admin`, `viewer` |
| `/complaints/*` | `jwt_admin` | Read | `viewer` |
| `/audit-templates/*` | `jwt_admin` | Read/Write | `admin` |
| `/analytics/*` | `jwt_admin` | Read | `viewer` |
| `/admin/*` | `jwt_admin` | Read | `admin` |

## Pages Covered

### P0 Critical (Must Test)

| Page ID | Route | Auth |
|---------|-------|------|
| `portal-login` | `/portal/login` | anon |
| `portal-home` | `/portal` | portal_sso |
| `portal-report` | `/portal/report` | portal_sso |
| `portal-report-incident` | `/portal/report/incident` | portal_sso |
| `portal-report-near-miss` | `/portal/report/near-miss` | portal_sso |
| `portal-report-rta` | `/portal/report/rta` | portal_sso |
| `login` | `/login` | anon |
| `dashboard` | `/dashboard` | jwt_admin |
| `incidents-list` | `/incidents` | jwt_admin |
| `incident-detail` | `/incidents/:id` | jwt_admin |
| `rtas-list` | `/rtas` | jwt_admin |
| `rta-detail` | `/rtas/:id` | jwt_admin |

### P0 Workflows (Must Test)

| Workflow ID | Description | Auth |
|-------------|-------------|------|
| `portal-incident-report` | Employee incident submission | portal_sso |
| `portal-near-miss-report` | Employee near-miss submission | portal_sso |
| `portal-rta-report` | Employee RTA submission | portal_sso |
| `admin-login` | Staff login flow | none (uses credentials) |
| `admin-view-incident` | Admin views incident details | jwt_admin |

## Security Policy

### Staging-Only Enforcement

- User MUST NOT exist in production database
- User email domain (`@staging.local`) blocked in production
- Token acquisition script ONLY calls staging endpoint

### Credential Management

| Policy | Requirement |
|--------|-------------|
| **Storage** | GitHub Actions Secrets only |
| **Rotation** | Every 30 days minimum |
| **Complexity** | Minimum 16 characters, mixed case + numbers + symbols |
| **Logging** | Credentials NEVER printed to logs |
| **Masking** | Tokens masked with `::add-mask::` |

### Misuse Prevention

- Account locked after 10 failed login attempts
- Session expires after 15 minutes inactivity
- Activity logged to audit trail (user ID only, not email)
- Account disabled immediately if used outside CI

### Rotation Procedure

1. Generate new password (use: `openssl rand -base64 24`)
2. Update staging database via admin console
3. Update GitHub Secret `UX_TEST_USER_PASSWORD`
4. Verify token acquisition succeeds
5. Document rotation in `ROTATION_LOG.md`

## GitHub Secrets Configuration

| Secret Name | Description |
|-------------|-------------|
| `UX_TEST_USER_EMAIL` | Test user email (e.g., `ux-test-runner@staging.local`) |
| `UX_TEST_USER_PASSWORD` | Test user password (rotated monthly) |

### Adding Secrets

1. Navigate to: Repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add each secret (values NEVER shared in documentation or chat)
4. Verify via workflow dispatch

## Validation Checklist

- [ ] User created in staging database
- [ ] Roles assigned: `user`, `employee`, `admin`, `viewer`
- [ ] User is active (`is_active = true`)
- [ ] User can authenticate via `/api/v1/auth/login`
- [ ] Token returned is valid (verified via `/api/v1/auth/whoami`)
- [ ] GitHub secrets configured
- [ ] Token acquisition job succeeds in CI
- [ ] All P0 routes accessible with token

## Troubleshooting

### Token Acquisition Fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Missing credentials` | Secrets not configured | Add GitHub secrets |
| `HTTP 401` | Wrong password | Verify/rotate password |
| `HTTP 403` | User inactive | Activate user in DB |
| `Request timeout` | Staging unreachable | Check staging health |

### Tests Skip Auth Routes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `tokens_acquired=false` | Token job failed | Check acquire-tokens logs |
| `Auth type not configured` | Token not passed | Verify workflow outputs |

## Audit Trail

| Date | Action | By |
|------|--------|-----|
| 2026-01-26 | Document created | Platform Team |

---

*This document is maintained by the Platform Team. For access requests or issues, contact @platform.*
