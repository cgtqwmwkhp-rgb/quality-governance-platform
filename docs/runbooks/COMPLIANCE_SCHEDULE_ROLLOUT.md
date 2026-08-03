# Compliance Schedule rollout

Skeleton runbook for the Compliance Schedule module. Expand with Wave 1 grant
procedure details and Wave 2 soak criteria before production enablement.

## Gates (two, subtract-only on the second)

| Gate | Mechanism | Default |
|---|---|---|
| Opener | `COMPLIANCE_SCHEDULE_ENABLED` / `settings.compliance_schedule_enabled` | `false` |
| Kill | `feature_flags.key = compliance_schedule_kill_switch` (`enabled=true` means **kill**) | no row / `false` |

The kill switch follows the AI Copilot pattern
(`src/domain/services/compliance_schedule_kill_switch.py`): 30s success TTL,
5s error retry, own session factory, sticky engaged on read failure. It
**cannot** open the module when configuration is off.

See also: [`AI_COPILOT_KILL_SWITCH.md`](./AI_COPILOT_KILL_SWITCH.md).

## Wave plan

### Wave 0 — Foundations (this PR)

- Schema: templates / requirements / records + RLS + `capasource.compliance_record`
- Catalogue seed from `specs/compliance-schedule/catalogue.json`
- Policy pure functions + unit tests
- Flag + kill switch + ADR-0020 + module brief

Nothing user-visible. Flag stays off.

### Wave 1 — Vertical slice (staging)

- API CRUD + complete-record; FE list/detail; evidence attach
- Permissions enforced on every route
- **Role grant procedure (placeholder):** apply the three tokens
  `compliance_schedule:read|create|update` to the admin role (or a dedicated
  compliance role) via a reviewed SQL/API change.  
  `ADMIN_ROLE_PERMISSIONS` in `src/domain/authz/catalogue.py` is a **proposal
  only** — nothing applies it automatically. Document the exact grant script
  here before staging demo to non-superusers.

### Wave 2 — Integrations

- CAPA writer from failed/missed records
- Calendar loader, notification sweep, library filing bridge
- Worker/beat redeploy, staging soak, then production flag on for Plantexpand

## Kill switch ladder

1. **Engage kill** (seconds): set `compliance_schedule_kill_switch.enabled = true`
   via feature-flags API or SQL. Wait ≤30s for all pods.
2. **Confirm:** module routes return unavailable / FE hides nav.
3. **Release kill:** set `enabled = false` (or delete the row). Reopens only if
   `COMPLIANCE_SCHEDULE_ENABLED` is still true.
4. **Hard close:** set `COMPLIANCE_SCHEDULE_ENABLED=false` and redeploy (opener).

## Rollback sketch

- Flag off + kill engaged → no user surface.
- Schema rollback: reverse `20260913_cs_wave0` only if no tenant data must be
  retained; `capasource` ADD VALUE is irreversible (label may remain unused).

## Related

- ADR-0020 occurrence model
- `docs/product/module-briefs.md` §42 Compliance Schedule
