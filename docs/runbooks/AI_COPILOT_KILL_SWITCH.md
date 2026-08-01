# AI Copilot kill switch runbook

Closes the AI Copilot in a running environment without a redeploy. Use it when the
copilot is saying something it should not and you need the surface shut in seconds
rather than in a release cycle.

## What it does

Every copilot HTTP route answers `404` and the chat WebSocket refuses the handshake
with close code `4004`, exactly as they do in an environment that never opted in. The
frontend already treats that `404` as unavailability — including part-way through an
open conversation, where the next message returns the unavailable notice and locks the
input — so no frontend change or redeploy is needed.

## What it cannot do

**It cannot turn the copilot on.** `AI_COPILOT_ENABLED` is checked first and short
circuits; the switch is only consulted once configuration has already said yes, and the
only thing it can say is no. Turning the copilot *on* still requires the environment
variable and a redeploy.

It also does not change the published OpenAPI document. The contract still describes the
copilot paths; requests to them return `404`. Unpublishing follows `AI_COPILOT_ENABLED`,
not the switch, so that the contract reflects what the environment is configured for
rather than flapping with an operational stop.

## Engaging it

The switch is the `copilot_kill_switch` row in `feature_flags`. `enabled = true` means
*the kill is engaged*, so no row and `enabled = false` both leave configuration in
charge. Only the `enabled` column is read — `rollout_percentage` and `tenant_overrides`
are ignored, because a partially applied kill is not a useful state.

### Option A — API (preferred; leaves a `feature_flag_toggle` audit entry)

Requires a superuser JWT.

```bash
# First time only: create the row.
curl -sS -X POST "$BASE/api/v1/feature-flags/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"key": "copilot_kill_switch", "name": "AI Copilot kill switch", "enabled": true}'

# Thereafter: engage or release.
curl -sS -X PATCH "$BASE/api/v1/feature-flags/copilot_kill_switch" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Option B — SQL (when the API is not usable)

```sql
INSERT INTO feature_flags (id, key, name, enabled)
VALUES (gen_random_uuid(), 'copilot_kill_switch', 'AI Copilot kill switch', true)
ON CONFLICT (key) DO UPDATE SET enabled = true, updated_at = now();
```

A direct SQL toggle is picked up on the same schedule as an API toggle, because the
copilot reads this row itself rather than going through `FeatureFlagService`'s
process-local flag cache.

## How long it takes to apply

Up to **30 seconds**. Each application process caches the verdict for that long so the
check costs one query per process per interval rather than one per request. There is no
need to restart anything; wait 30 seconds and re-check.

## Releasing it

Set `enabled = false` (or delete the row). The copilot reopens within the same 30
seconds, provided `AI_COPILOT_ENABLED` is still set for that environment.

## Behaviour when the database is unreachable

- A kill **already observed** by a process stays engaged. An infrastructure failure
  cannot reopen a surface an operator deliberately closed; only a successful read saying
  `enabled = false` clears it.
- A kill **never observed** is treated as not engaged, and the copilot continues to
  follow `AI_COPILOT_ENABLED`. This is deliberate: failing closed here would take the
  copilot down on any database wobble, and the surface is only open in the first place
  because an operator explicitly set the environment variable.

Failed reads are logged as a warning from
`src.domain.services.copilot_kill_switch` — `"AI Copilot kill switch could not be read"`
— with the exception type and which way it was resolved. If you engage the switch and
the copilot keeps answering, search for that line first.

## Verifying

```bash
# Expect 404 once engaged (any authenticated caller, or none at all).
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/api/v1/copilot/actions"
```

## Related

- `AI_COPILOT_ENABLED` — the configuration gate. Off by default in every environment.
- `src/domain/services/copilot_kill_switch.py` — the switch, and why it does not reuse
  `FeatureFlagService`.
