# Secrets Rotation Runbook

## Overview
This runbook documents the procedure for rotating all application secrets and credentials.

## Secret Inventory

| Secret | Location | Rotation Frequency | Owner |
|--------|----------|-------------------|-------|
| DATABASE_URL | Azure Key Vault / .env | 90 days | Platform Team |
| JWT_SECRET_KEY | Azure Key Vault / .env | 90 days | Security Team |
| AZURE_AD_CLIENT_SECRET | Azure AD / .env | 365 days | Identity Team |
| PSEUDONYMIZATION_PEPPER | Azure Key Vault / .env | Never (hash-breaking) | Security Team |
| SMTP credentials | Azure Key Vault / .env | 180 days | Platform Team |
| API keys (3rd party) | Azure Key Vault / .env | Per vendor policy | Platform Team |

## Rotation Procedures

### 1. Database Password Rotation
1. Generate new password: `openssl rand -base64 32`
2. Update in Azure Database for PostgreSQL
3. Update DATABASE_URL in Azure Key Vault
4. Restart application containers
5. Verify connectivity: `curl https://app/api/v1/readyz`
6. Update local .env files for development team

### 2. JWT Secret Rotation
1. Generate new secret: `openssl rand -hex 64`
2. Deploy new secret alongside old (dual-validation window: 24h)
3. After 24h, remove old secret
4. All active sessions will require re-authentication

### 3. Azure AD Client Secret
1. Navigate to Azure AD > App Registrations > Quality Governance Platform
2. Generate new client secret (recommended: 2-year expiry)
3. Update in Key Vault and application config
4. Test SSO login flow end-to-end

## Post-Rotation Checklist
- [ ] New secret deployed to all environments (dev, staging, prod)
- [ ] Health check passing
- [ ] Login flow verified
- [ ] Monitoring alerts confirmed (no auth failures)
- [ ] Old secret revoked/deleted
- [ ] Rotation logged in audit trail
