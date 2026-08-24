# Phase 2 walk-away data cleanup evidence (PX-177 soft-delete)

**Date:** 2026-08-02  
**Operator path:** `scripts.ops.run021.soft_delete_walkaway_debris` (ComplaintService / IncidentService / action soft-delete)  
**Actor:** `david.harris@plantexpand.com`  
**Request IDs:** `walkaway-phase2-stg-20260802`, `walkaway-phase2-prod-20260802`

## Scope

| Board / lane | Target | Env |
|---|---|---|
| w6-residue-prod | `COMP-2026-0007` (id 11), `INA-2026-45D06064` (id 7) | production |
| w6-residue-stg | `COMP-2026-0018` (id 18) | staging |
| PX-125 debris | titles starting `[PURGED-RUN021]` plus `INC-2026-0058` / `0059` / `0060` | both |

Hard delete was not used. Rows retain reference numbers; `deleted_at` / `deleted_by_id` set via PX-177 product services.

## Before (live, `deleted_at IS NULL`)

### Production

| Kind | Count | Notes |
|---|---:|---|
| Complaints | 6 | 5× `[PURGED-RUN021]` + `COMP-2026-0007` |
| Incidents | 21 | 20× `[PURGED-RUN021]` + `INC-2026-0058/59/60` (0059 had no purge prefix) |
| Incident actions | 1 | `INA-2026-45D06064` id 7 (parent `INC-2026-0060` id 134) |

### Staging

| Kind | Count | Notes |
|---|---:|---|
| Complaints | 18 | 17× `[PURGED-RUN021]` + `COMP-2026-0018` |
| Incidents | 45 | all `[PURGED-RUN021]` titled |
| Incident actions | 0 | — |

## After (independent SQL verify)

Live remaining for all target predicates: **0** on both environments.

### Production key rows

| Ref | id | deleted_at (UTC) | deleted_by_id |
|---|---:|---|---:|
| COMP-2026-0007 | 11 | 2026-08-02T19:41:17.852055Z | 1 |
| INA-2026-45D06064 | 7 | 2026-08-02T19:40:37.273939Z | 1 (cascade from INC-0060) |
| INC-2026-0058 | 126 | 2026-08-02T19:40:45.199254Z | 1 |
| INC-2026-0059 | 132 | 2026-08-02T19:40:35.525855Z | 1 |
| INC-2026-0060 | 134 | 2026-08-02T19:40:37.273939Z | 1 |

Soft-deleted `[PURGED-RUN021]` titles still present as archived rows: **20** incidents, **5** complaints.

### Staging key rows

| Ref | id | deleted_at (UTC) | deleted_by_id |
|---|---:|---|---:|
| COMP-2026-0018 | 18 | 2026-08-02T19:39:35.007006Z | 3 |

Soft-deleted `[PURGED-RUN021]` titles still present as archived rows: **45** incidents, **17** complaints.

## Manifests (operator machine)

- `/tmp/walkaway-stg-dryrun.json`
- `/tmp/walkaway-stg-apply.json`
- `/tmp/walkaway-prod-dryrun.json`
- `/tmp/walkaway-prod-apply.json`

## Blocked / out of scope

- No API bearer token path used (prod local-password login disabled; Entra token-exchange not exercised). DB + service-layer path used instead.
- Document campaigns / other non-PX-177 tables with purge prefixes were **not** mutated.
- Firewall rule `qgp-phase2-cleanup-20260802` was temporary for this session and must be removed after closeout.
