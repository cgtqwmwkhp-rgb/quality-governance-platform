# Human unlock — agent close-out evidence (2026-07-12)

## What agent completed (no invented secrets)

| Track | Result |
|-------|--------|
| A SMTP | Wire script + runbook landed; KV/App Settings still empty of SMTP; `/readyz` still `email_configured=false` |
| B PagerDuty | Same script supports optional `PAGERDUTY_ROUTING_KEY`; status still `not_configured` |
| C Dependabot | Closed #558 #287 #274 #573 with skip rationale; opened #851 (FE toolchain) + #852 (bcrypt 5) |
| D DPIA/EA-03 | Prepared `docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md` (unsigned); tracker updated |

## Baseline curl (pre-secret)

```
prod email_configured=false · pagerduty=not_configured · readyz ready
staging same honesty
```

## Human residual (required for LIVE score credit)

1. Export real `SMTP_USER` / `SMTP_PASSWORD` / `FROM_EMAIL` and run:
   `./scripts/ops/wire_smtp_pagerduty.sh staging` then `... prod`
2. Prove enqueue → SUCCESS; then canvas-credit S4/S11/S12
3. Export `PAGERDUTY_ROUTING_KEY` and re-run script (or set KV); prove configured + test page
4. DPO completes signature block in EA-03 evidence file; engineering then flips `privacy.py` status

Artifacts:
- `scripts/ops/wire_smtp_pagerduty.sh`
- `docs/runbooks/HUMAN_UNLOCK_SMTP_PAGERDUTY.md`
- `docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md`
