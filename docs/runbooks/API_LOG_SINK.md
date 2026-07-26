# API log sink (Log Analytics)

Both API App Services stream request, console, application and audit logs to Log Analytics
through a diagnostic setting named `qgp-api-logs`.

| App | Resource group | Workspace |
|-----|----------------|-----------|
| `app-qgp-prod` | `rg-qgp-staging` | `workspace-rgqgpprodFJuX` (`rg-qgp-prod`) |
| `qgp-staging-plantexpand` | `rg-qgp-staging` | `workspace-rgqgpprodFJuX` (`rg-qgp-prod`) |

Categories: `AppServiceHTTPLogs`, `AppServiceConsoleLogs`, `AppServiceAppLogs`,
`AppServiceAuditLogs`.

The Celery worker and beat use a **different** setting (`celery-logs`, console + platform
logs) for reasons set out in `scripts/infra/ensure_log_sink.sh`. The two are deliberately
distinct: HTTP logs on a worker would record nothing but AlwaysOn pings, and platform logs
are what make a failed container pull visible. Do not merge them.

Staging currently streams to the *production* workspace. That is the state that was
applied by hand and is what the scripts reproduce, but it means staging telemetry lands in
the production workspace — worth revisiting.

## Who maintains it

`scripts/infra/ensure_api_log_sink.sh` creates the setting idempotently and warns if it is
missing. It runs from:

- `.github/workflows/deploy-production.yml` and `deploy-staging.yml`, on every deploy
- `.github/workflows/provision-production.yml`, when production is provisioned

The deploy is the primary enforcement point, because nothing in the repo provisions
`qgp-staging-plantexpand` at all, and `infra/main.bicep` names (`qgp-production-api`,
`qgp-staging-api`) do not match any live resource.

## Reading the logs

```bash
WSID=$(az monitor log-analytics workspace show -g rg-qgp-prod \
  -n workspace-rgqgpprodFJuX --query customerId -o tsv)
az monitor log-analytics query --workspace "$WSID" --analytics-query "
AppServiceHTTPLogs
| where TimeGenerated > ago(1h)
| where _ResourceId has 'app-qgp-prod'
| project TimeGenerated, CsMethod, CsUriStem, ScStatus, TimeTaken, CIp
| order by TimeGenerated desc"
```

Note the deliberate omission of `CsUriQuery` from that projection — see below.

## Query strings are recorded: what that means here

`AppServiceHTTPLogs` records the raw query string in the `CsUriQuery` column. Anyone with
read access to the workspace can read it. Capture happens in the App Service front end, so
**no application-level redaction can prevent it** — middleware in `src/` runs too late and
cannot see, let alone alter, what the platform writes.

The following query parameters on this API therefore end up in Log Analytics.

### Credentials in query strings

| Parameter | Endpoint | Assessment |
|-----------|----------|------------|
| `token` | `GET /api/v1/realtime/ws/{user_id}?token=<JWT>` (`src/api/routes/realtime.py`) | **A live JWT access token.** `frontend/src/hooks/useWebSocket.ts` puts the platform token in the query string for every browser WebSocket connection; the same file redacts it before writing to the browser console, so the sensitivity is already understood. Access tokens expire after 30 minutes (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`), which bounds but does not remove the replay window. |
| `tracking_code` | `GET /api/v1/portal/reports/{reference_number}/?tracking_code=…` (`src/api/routes/employee_portal.py`) | **A permanent credential.** `generate_tracking_code` is `HMAC(SECRET_KEY, "portal-track:" + reference_number)`, deterministic and with no expiry — it only changes if `SECRET_KEY` rotates. It is the sole authentication for an anonymous portal report, so a logged value grants indefinite read access to that report's status and timeline. This is the anonymous whistleblowing channel, which makes it the most sensitive of the three. |
| `sig`, `key`, `expires` | `GET /api/v1/evidence-assets/download` (`src/api/routes/evidence_assets.py`) | An HMAC signature over a storage key. **Inert in both deployed environments**: the handler rejects with `NOT_AVAILABLE` unless storage is `LocalFileStorageService`, and both production and staging set `AZURE_STORAGE_CONNECTION_STRING`, so `storage_service()` returns `AzureBlobStorageService`. The signature is still written to the log, so this becomes live if local storage is ever used in a deployed environment. Azure SAS URLs are unaffected — they point at `*.blob.core.windows.net` and never reach this app's HTTP log. |

### Personal data in query strings

| Parameter | Endpoints | Content |
|-----------|-----------|---------|
| `reporter_email` | `/api/v1/incidents/`, `/api/v1/rtas/`, `/api/v1/near-miss/` | Email address of an incident reporter |
| `complainant_email` | `/api/v1/complaints/` | Email address of a complainant |
| `q` | `/api/v1/users/search/` | Matched against email, first name and last name, so in practice contains staff names |
| `q` | `/api/v1/search/`, `/api/v1/documents/…`, `/api/v1/notifications/…`, `/api/v1/investigations/…` | Free text up to 200 characters, typically a person, vehicle or case reference |
| `query` | `/api/v1/copilot/…` | Free text |
| `search` | risk register, compliance, vehicle checklists, document control | Free text, matched against owner names among other fields |

`reporter_email` and `complainant_email` are also exercised directly by the post-deploy
security checks in `deploy-production.yml`, which curl them with `test@example.com`.

### What this does not cover

Request and response **bodies are not logged** — only the method, URI, query string, status,
timing and client IP. Case narratives submitted in a POST body do not appear in
`AppServiceHTTPLogs`.

This also means HTTP logs alone are **not** a record of what was sent to the third-party AI
processors. Those are outbound calls from the application; evidencing them for a UK GDPR
record of processing needs application-level logging in `AppServiceAppLogs` /
`AppServiceConsoleLogs`, not the HTTP log.

## Handling the exposure

Until the query-string credentials are moved out of the URL, treat the workspace as
holding credential material:

- Keep workspace read access limited to those who already have production access. A
  `CsUriQuery` value is as good as a session for the endpoints above.
- Do not paste `CsUriQuery` into tickets, dashboards or shared queries. Project the
  columns you need, as the query above does.
- 30-day workspace retention bounds how long a `tracking_code` stays readable. Raising
  retention lengthens that exposure as well as the audit trail.

The durable fixes are application changes and are deliberately **not** in this PR, since
`src/api/routes/employee_portal.py` and the portal frontend are being worked on
concurrently:

1. Move the WebSocket token out of the query string — the endpoint already prefers an
   `Authorization: Bearer` header (`_extract_websocket_token`), so this is a frontend
   change plus removing the `?token=` fallback.
2. Accept the portal tracking code as a header or POST body rather than a query parameter,
   and give it an expiry.
