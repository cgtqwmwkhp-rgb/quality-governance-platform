# Run021 Ops Park Runbook

**Lane:** O (ops dry-run + runbook)  
**Base tip:** `origin/main` @ `a52f4287` (at authoring)  
**Scope:** scripts + docs only — **no** `src/**`, `frontend/**`, or `alembic/**` changes in this PR.

This runbook covers residual **data / ops** work that honesty banners already disclose in product. It does **not** replace schema/mint code lanes (Lane S) or UVDB/export lanes.

---

## Absolute safety rules

1. **Dry-run is the default.** Every script under `scripts/ops/run021/` reports a plan and writes **nothing** unless `--apply` is passed.
2. **Human approval is required before any `--apply` on staging or production.** Name the approver in the change ticket / ops log.
3. **Production additionally requires `--i-understand-prod`.** Without it, scripts refuse `--apply` when `APP_ENV` / `ENVIRONMENT` / `QGP_ENV` looks like `production` / `prod` / `live`.
4. **Never use `--admin` as a shortcut** and never wire these scripts into CI deploy / conveyor write jobs. CI may lint/import-check only.
5. Prefer **soft** remediation (deactivate, archive, close, prefix `[PURGED-RUN021]`) over hard deletes. PX-266 hard delete requires an extra `--hard-delete-fixtures` flag.
6. Take a **DB backup / PITR recovery point** before any prod `--apply`.

---

## Script map

| Script | PX | What it does |
|--------|----|--------------|
| `inventory_test_debris.py` | 125, 192, 197, 239, 221, 266, 275 | Read-only inventory of UAT/CUJ/smoke debris |
| `purge_test_debris.py` | same | Dry-run purge plan; `--apply` soft-closes / deactivates / archives |
| `soft_delete_walkaway_debris.py` | 125 / 177 / residue | PX-177 soft-delete for `[PURGED-RUN021]` titles + walk-away residue refs (COMP-0007/0018, INA-45D06064, INC-0058/59/60) |
| `remint_hex_references.py` | 126 | Hex `PREFIX-YYYY-XXXXXXXX` → sequential `PREFIX-YYYY-NNNN` mapping (+ ledger) |
| `verify_reseed_portal_templates.py` | 306 | Verify published portal slugs; dry-run / minimal re-seed |
| `library_to_doc_control_drafts.py` | 263 | Library policy docs → Document Control **drafts** |
| `inventory_ops_backlog.py` | 157, 264, 246, 273 (+271 hours) | Read-only backlog inventories for human ops |

Invoke from repo root with `DATABASE_URL` set (read-only credentials are enough for dry-run):

```bash
python -m scripts.ops.run021.inventory_test_debris --json
python -m scripts.ops.run021.purge_test_debris            # dry-run
python -m scripts.ops.run021.soft_delete_walkaway_debris  # PX-177 soft-delete dry-run
python -m scripts.ops.run021.remint_hex_references
python -m scripts.ops.run021.verify_reseed_portal_templates
python -m scripts.ops.run021.library_to_doc_control_drafts
python -m scripts.ops.run021.inventory_ops_backlog --json
```

Apply example (**staging first**, after named approval):

```bash
python -m scripts.ops.run021.purge_test_debris --apply
python -m scripts.ops.run021.soft_delete_walkaway_debris --apply \
  --manifest /tmp/walkaway-stg.json --actor-email david.harris@plantexpand.com
# production only after backup + written approval:
python -m scripts.ops.run021.purge_test_debris --apply --i-understand-prod
python -m scripts.ops.run021.soft_delete_walkaway_debris --apply --i-understand-prod \
  --manifest /tmp/walkaway-prod.json --actor-email david.harris@plantexpand.com
```

---

## Recommended order of operations

### 1) Inventory (no writes)

1. `inventory_test_debris` — capture counts for PX-125/192/197/239/221/266/275.
2. `inventory_ops_backlog` — capture PX-157/264/246/273/271 evidence packs.
3. `verify_reseed_portal_templates` — confirm PX-306 slug health (exit 1 if missing/unpublished).
4. `remint_hex_references` dry-run — count hex refs (PX-126). Prefer completing **Lane S mint fix** before reminting so new portal rows stop creating hex.
5. `library_to_doc_control_drafts` dry-run — list Library→draft candidates (PX-263).

Attach JSON outputs to the ops ticket.

### 2) Staging apply (human-approved)

1. Backup staging DB.
2. Apply purge (soft) → spot-check registers / admin users / templates / groups.
3. Apply portal template publish/stub only if verification still fails **and** alembic `20260827_lookup_tenant_fix` is already on the env (prefer full migration seed over stubs).
4. Apply Library→drafts; confirm Document Control shows drafts, still empty of *approved* controlled docs until humans progress workflow.
5. Remint hex refs **after** mint fix is live on that environment; keep the `system_settings` ledger key `ops.run021.px126_remint_mapping`.

### 3) Production apply (separate approval)

Same sequence. Require:

- Named human approver
- `--apply --i-understand-prod`
- Post-apply smoke: incidents/complaints lists, portal intake network (no template 404), Document Control drafts, admin users inactive for **debris** smoke accounts
- **Do not** soft-purge dedicated CI runners listed in `CI_SMOKE_USER_EMAILS` (`ux-test@example.com`, `smoke-runner@plantexpand.com`, …). Deactivating them returns `ACCOUNT_LOCKED` and blocks staging→prod promotion.

### 4) Human-only follow-ups (scripts only inventory)

| PX | Human action |
|----|--------------|
| PX-157 | Assess / review risks still `last_review_date IS NULL` |
| PX-264 | Accept/reject + assign owners on audit-import triage queue |
| PX-246 | Upload Planet Mark evidence / set YE2025 certification status with assessor |
| PX-273 | Answer open HSEQ inbox threads |
| PX-271 | Correct 2024 annual hours in Admin HS reporting (AFR denominator) |

---

## Acceptance criteria (this PR)

- [x] **AC-01** Every Run021 ops script defaults to dry-run (no writes without `--apply`).
- [x] **AC-02** Prod-looking envs refuse `--apply` unless `--i-understand-prod` is also set.
- [x] **AC-03** Inventory coverage exists for PX-125, 192, 197, 239, 271, 275, 221, 266, 126, 306, 263, 157, 264, 246, 273.
- [x] **AC-04** No `src/**`, `frontend/**`, or `alembic/**` changes in this PR.
- [x] **AC-05** Runbook documents human approval before any staging/prod `--apply`.

---

## Rollback notes

| Action | Rollback |
|--------|----------|
| Soft purge (title prefix / close / deactivate) | Reverse status / strip prefix / re-activate from ledger JSON |
| PX-266 archive | Set template status back to `published` if still needed |
| PX-266 hard delete | Restore from backup only |
| PX-126 remint | Use `ops.run021.px126_remint_mapping` to restore `old` refs |
| PX-306 stub insert | Unpublish / delete stub slug if full migration seed replaces it |
| PX-263 drafts | Delete draft `controlled_documents` rows created with `DRAFT-LIB-*` numbers |

---

## Out of scope (other lanes)

- PX-210 / PX-222 / PX-126 **mint** — Lane S (schema + ReferenceNumberService)
- PX-255 / PX-244 — Lane U (UVDB)
- PX-160 — Lane X (Export Center APIs)
- PX-177 / PX-220 / PX-244 content — human / content owners
