# Secret rotation runbook (D19 — Configuration management)

This runbook covers secrets for the **Quality Governance Platform** on Azure App Service, with configuration loaded from environment variables / **Azure Key Vault** references. Settings are defined in `src/core/config.py` (`Settings` / `get_settings()`).

## Secrets inventory

| Secret / variable | Used for | Typical storage |
|-------------------|----------|-----------------|
| `SECRET_KEY` | Session/signing and other app-level secrets derived from core app key (`secret_key` in `Settings`). | Key Vault → App Service setting |
| `JWT_SECRET_KEY` | Signing **platform JWTs** (access/refresh) — `jwt_secret_key`. | Key Vault → App Service setting |
| `DATABASE_URL` | Async SQLAlchemy URL for primary **PostgreSQL** (`database_url`). | Key Vault → App Service setting (often Key Vault reference) |
| `REDIS_URL` | Redis for rate limiting, idempotency, optional caches (`redis_url`). | Key Vault → App Service setting |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure Monitor / OpenTelemetry export (`applicationinsights_connection_string`). | Key Vault → App Service setting |
| `PSEUDONYMIZATION_PEPPER` | GDPR pseudonymization salt/pepper (`pseudonymization_pepper`); min length validated in `Settings`. | Key Vault → App Service setting |
| **Azure AD client secret** | Confidential client flows if used (not always required for SPA + ID token validation); sync with `AZURE_CLIENT_ID` / tenant settings. | Key Vault; rotate in **App registrations** |
| **PAMS credentials** | `PAMS_DATABASE_URL` (MySQL DSN, includes user/password) and optional `PAMS_SSL_CA` (certificate material). | Key Vault → App Service setting |

**Related sensitive configuration** (rotate with the same discipline):

| Variable | Notes |
|----------|--------|
| `AZURE_STORAGE_CONNECTION_STRING` | Blob/attachment storage. |
| `EMAIL_USERNAME` / `EMAIL_PASSWORD` | IMAP ingestion (`Settings`). |
| `SMTP_USER` / `SMTP_PASSWORD` | Outbound email (`EmailService` / env). |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Often contain credentials in the URL. |

## Rotation schedule

| Item | Cadence / rule |
|------|----------------|
| `JWT_SECRET_KEY` | **Every 90 days** (coordinate with token TTL and client logout). |
| **Database password** (embedded in `DATABASE_URL`) | **Every 180 days** (or per organisational policy). |
| **Azure AD client secret** | **Before expiry** — monitor in Azure Portal → App registration → Certificates & secrets. |
| `PSEUDONYMIZATION_PEPPER` | **NEVER rotate** in place. Changing it **breaks** existing pseudonymous identifiers/hashes. If compromised, treat as a **data migration** project with legal/DPO sign-off. |

All other secrets: rotate on **compromise**, **personnel change**, or **vendor recommendation**.

## Rotation procedure (standard)

For each secret type, follow this pattern:

1. **Generate new value**  
   - Symmetric keys: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`  
   - Database: create new DB user password in the managed database tier.  
   - Azure AD: create a **new** client secret in the portal; note expiry.

2. **Update in Azure Key Vault**  
   - Add a **new version** of the secret (retain old version until verification).  
   - Update App Service application settings to reference the new version if not using “latest”.

3. **Restart App Service (zero-downtime via slot swap)**  
   - Deploy the setting change to **staging slot** first.  
   - Warm the slot; run verification (below).  
   - **Swap** staging ↔ production.  
   - Alternatively: update production slot settings and restart that slot during a window if slots are unavailable.

4. **Verify**  
   - **`GET /readyz`** — database connectivity; Redis reported as `ok`, `degraded`, or `not_configured` per `src/api/routes/health.py`.  
   - **`GET /api/v1/auth/whoami`** (with a valid Bearer token) — confirms JWT validation and DB-backed user load after `JWT_SECRET_KEY` or DB changes (`src/api/routes/auth.py`).

5. **Invalidate old value**  
   - Disable/remove previous Azure AD secret **after** all instances use the new one.  
   - For DB: revoke old password only after connection strings updated everywhere (App Service, workers, migration jobs).  
   - For Key Vault: optionally disable old secret version per retention policy.

### Per-secret notes

- **`JWT_SECRET_KEY`** — After rotation, **existing** access tokens signed with the old key become invalid unless you run a dual-signing period (not implemented by default). Plan for **forced re-login** or refresh-token rotation window.  
- **`SECRET_KEY`** — Any artefact tied to this key (e.g. legacy signed cookies) invalidates on change; restart all workers.  
- **`DATABASE_URL`** — Use connection pooling friendly rollover: update URL, deploy, verify `/readyz`, then revoke old DB password.  
- **`REDIS_URL`** — Updating auth string drops in-flight idempotency keys; acceptable briefly; monitor 409/idempotency behaviour.  
- **`APPLICATIONINSIGHTS_CONNECTION_STRING`** — Telemetry may gap during rollover; no user impact.  
- **PAMS** — Update `PAMS_DATABASE_URL`; verify `/readyz` `pams` check and a vehicle checklist endpoint.

## Emergency rotation (suspected compromise)

1. **Assume breach** — Revoke or disable the compromised secret **immediately** in Key Vault / Azure AD / database console where possible.  
2. **Issue replacement** — New secret value **out of band**; do not commit to git.  
3. **Blast radius** — Rotate **downstream** creds that could have been derived (DB app user, Redis ACL password, SMTP, storage keys) if the leak could expose them.  
4. **Deploy fast** — Update **all** App Service instances and **Celery workers** using the same env.  
5. **Invalidate sessions** — For `JWT_SECRET_KEY` or `SECRET_KEY` compromise, treat all sessions as suspect: deploy new keys, clear client storage, monitor `auth.failures` / login metrics.  
6. **Forensics** — Export Azure **Activity Log** and Key Vault **audit logs** for the incident window (see below).  
7. **Post-incident** — Document root cause; add detection (e.g. failed auth spike, unusual Key Vault access).

## Configuration change audit

| Source | What to review |
|--------|----------------|
| **Azure Activity Log** | Who changed App Service configuration, slot swaps, restarts. |
| **Key Vault logging** | `Microsoft.KeyVault/vaults/*/read` / write events; failed access attempts. |
| **Application Insights** | Anomalies after deploy (5xx, auth errors). |

Enable diagnostic settings to send Key Vault and App Service audit logs to Log Analytics or a SIEM if not already enabled.

## Environment validation (fail-fast)

Production safety checks are implemented in **`Settings._validate_production_settings()`** in `src/core/config.py`:

- **`SECRET_KEY` / `JWT_SECRET_KEY` / `PSEUDONYMIZATION_PEPPER`** must not match known **placeholder** strings in production (`change-me-in-production`, `changeme`, etc.).  
- **`DATABASE_URL`** must be set in production and must **not** point to `localhost` or `127.0.0.1`.  
- **`DATABASE_URL`** must start with `postgresql` or `sqlite` (format guard for all environments).  
- **`PSEUDONYMIZATION_PEPPER`** must be **≥ 16 characters** (`validate_pepper_length`).  

If any check fails, the process **raises** at startup — this is intentional **fail-fast** behaviour to avoid running a misconfigured production tier.

---

*Configuration reference:* `src/core/config.py` · *Readiness checks:* `GET /readyz` in `src/api/routes/health.py` · *Auth smoke test:* `GET /api/v1/auth/whoami` in `src/api/routes/auth.py`.
