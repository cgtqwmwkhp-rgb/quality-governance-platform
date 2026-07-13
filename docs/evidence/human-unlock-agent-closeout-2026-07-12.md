# Human unlock agent closeout — 2026-07-12 (historical)

Superseded notes for the SMTP/PagerDuty human-unlock track.

| Item | Outcome |
|------|---------|
| A SMTP | Wired and proven LIVE on staging + prod (Celery `status=sent`) |
| B PagerDuty | **Cancelled 2026-07-13 (EA-05)** — Events API path removed from product; do not wire |

## Current ops paths

- SMTP: `scripts/ops/wire_smtp.sh` + [`docs/runbooks/HUMAN_UNLOCK_SMTP.md`](../runbooks/HUMAN_UNLOCK_SMTP.md)
- Alerting: Azure Monitor email action groups — [`docs/runbooks/alerting-integration.md`](../runbooks/alerting-integration.md)
- Attestation SSOT: [`external-attestation-tracker.md`](external-attestation-tracker.md) (EA-05 Cancelled)
