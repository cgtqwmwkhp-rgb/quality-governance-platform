# Inspection → CAPA → Risk CUJ — staging walkthrough

**App:** https://qgp-staging-plantexpand.azurewebsites.net  
**Do not use** `app-qgp-staging`. Prod is for tip==prod confirmation only.

## Operator click-path (live inspection)

1. Open `/audits` → Schedule New Audit from a published template with **auto_create_findings** and questions that **failure_triggers_action**.
2. Open `/audits/{id}/execute` (or mobile). Answer a mix of **pass** and **fail**.
3. Complete the run. If any finding has `corrective_action_required`, expect navigation toward `/actions`.
4. On `/actions`, open the CAPA item. Confirm `source_type=audit_finding` and matching `source_id`.
5. Open `/audits?view=findings`. From a finding card:
   - **Open CAPA** → `/actions?sourceType=audit_finding&sourceId={id}`
   - **Open risk register** → `/risk-register?auditOnly=1&auditRef={finding.reference_number}`
6. On `/risk-register`, confirm organisational risk(s) linked to the finding/run refs.
7. Optional second path: External Import → `/audits/{id}/import-review` → promote → DownstreamWorkflowProof → Risk Register **Import triage** accept/reject.

## API proof (replace TOKEN)

```bash
STG=https://qgp-staging-plantexpand.azurewebsites.net
AUTH="Authorization: Bearer $TOKEN"

# Findings
curl -sS -H "$AUTH" "$STG/api/v1/audits/findings?page=1&page_size=20" | jq '.items[0]|{id,reference_number,corrective_action_required,risk_ids,severity,finding_type}'

# CAPA via unified actions
FID=123  # finding id
curl -sS -H "$AUTH" "$STG/api/v1/actions?source_type=audit_finding&source_id=$FID" | jq .

# Risk register (client filters by auditRef; list then filter)
curl -sS -H "$AUTH" "$STG/api/v1/risk-register/?page=1&page_size=50" | jq .

# Explicit flag to org risk (after flag-risk PR lands)
# curl -sS -X POST -H "$AUTH" -H "Content-Type: application/json" \
#   "$STG/api/v1/audits/findings/$FID/flag-risk" -d '{"severity":"high"}' | jq .
```

## Expected behaviour

| Finding class | CAPA | Org risk |
|---------------|------|----------|
| Positive / OFI / observation | No auto-CAPA | No auto-risk after risk-gate PR; explicit flag only |
| Nonconformity + corrective_action_required | Auto CAPA | Auto for severity critical\|high\|medium\|low |
| Significant issue flagged manually | Optional CAPA | Explicit `flag-risk` → risks_v2 |

## Out of scope on this walk

- Email / SMTP assignment notifications (parked)
- Legacy `/risks` UI (redirects to `/risk-register`)
