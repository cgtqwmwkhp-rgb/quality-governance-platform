# Assessor CUJ proof checklist (staging / prod)

**Status:** SCAFFOLD ONLY — do **not** mark LIVE until every step below is verified on the target environment and evidence is linked.

**Feature:** Operational Standards Assessor → Knowledge Exceptions inbox  
**App (staging):** https://qgp-staging-plantexpand.azurewebsites.net  
**Do not use** `app-qgp-staging`. Prod only after tip==prod confirmation.

## Operator click-path (primary CUJ)

1. Open an existing staging **incident** (`/incidents/{id}`) → **Standards** tab.
2. Click **Assess against standards**.
3. Expect proposed clause link(s) with signal type (typically **nonconformity** for incidents) and optional related KB documents.
4. Open related document link → should land on `/documents/{id}?tab=evidence` (Standards & Evidence).
5. Open **Knowledge Exceptions** (`/knowledge-exceptions`).
6. Confirm the proposed NC/gap/etc. appears. Use filters:
   - **Entity type** = Incident (server `entity_type` query)
   - **Signal type** = Nonconformity (client-side on loaded page ≤200; no fake totals)
7. **Confirm** or **Reject** one item (panel and/or Exceptions bulk actions).
8. Reload Exceptions — confirmed/rejected item must leave the default proposed/needs_review inbox.

Repeat optionally for complaint / near_miss / RTA / audit_finding when available.

## API proof (replace TOKEN — never commit secrets)

```bash
STG=https://qgp-staging-plantexpand.azurewebsites.net
AUTH="Authorization: Bearer $TOKEN"
ENTITY_TYPE=incident
ENTITY_ID=123   # real staging id

# Assess
curl -sS -X POST -H "$AUTH" -H "Content-Type: application/json" \
  "$STG/api/v1/knowledge-bank/entities/$ENTITY_TYPE/$ENTITY_ID/assess" \
  -d '{}' | jq '{signal_type, links_created, related: (.related_documents|length)}'

# Exceptions inbox (entity filter — supported)
curl -sS -H "$AUTH" \
  "$STG/api/v1/knowledge-bank/exceptions?entity_type=$ENTITY_TYPE" \
  | jq 'map({id, entity_type, entity_id, signal_type, status, clause_id})'

# Full inbox page (signal_type present on rows; server has no signal_type= filter yet)
curl -sS -H "$AUTH" "$STG/api/v1/knowledge-bank/exceptions" \
  | jq 'map(.signal_type) | unique'
```

## Expected behaviour

| Step | Expected |
|------|----------|
| Assess operational entity | Always **proposed** (never silent auto-confirm) |
| Exceptions list | Shows proposed / needs_review only (default) |
| Entity filter | Hits API `?entity_type=` |
| Signal filter | Client-side on loaded rows; showing count is of loaded page only |
| Confirm / reject | Item leaves inbox |

## Known API gaps (Follow-up A / #922)

- `GET /api/v1/knowledge-bank/exceptions` supports `status` + `entity_type` but **not** `signal_type` as a query param.
- No honest server-side total/facet counts for signal types until backend adds them.

## Verification record (fill when run)

| Field | Value |
|-------|-------|
| Environment | staging / prod |
| Date (UTC) | |
| Operator | |
| Incident / entity id | |
| Links created | |
| Exceptions confirm/reject OK? | ☐ |
| Evidence links (screenshot / curl log path) | |
| LIVE claim allowed? | **NO** until this row is complete |

## Out of scope on this walk

- IMS coverage math / re-weighting (Follow-up A)
- Complaint/RTA/near-miss auto-hooks beyond manual Assess
- Inventing facet counts or LIVE attestation without evidence
