# Runbook — purging duplicate audit runs (FR-DEDUP-01)

Hard-deletes a named duplicate audit and everything belonging to it, and scans the
audit, risk, action and case registers for other duplicates.

| | |
|---|---|
| Scripts | `scripts/ops/run027/purge_duplicate_audit_runs.py`, `scripts/ops/run027/inventory_duplicate_registers.py` |
| Tests | `tests/unit/test_run027_duplicate_audit_purge.py` |
| Requires | Direct database access. **Not** wired into CI, deploy, or the conveyor. |
| Default | Dry run. `--apply` is opt-in and needs `--i-understand-prod` on production. |

> **This was not executed against production.** The environment the change was
> authored in has no `DATABASE_URL` and no route to the production database. The
> scripts, the refusals and the runbook below are the deliverable; an operator with
> database access performs the run.

---

## 1. What FR-DEDUP-01 authorises

Production shows the same B2 audit for Plantexpand Limited three times. All three
carry the title `B2 Audit - 2026-02-20T00:00:00 - Kevin Game`, a score of 97.7%, and
status `completed`.

| Reference | Disposition |
|---|---|
| `AUD-2026-0043` | **Purge.** Re-import. |
| `AUD-2026-0048` | **Purge.** Re-import. |
| the earlier audit that was subsequently updated | **Survives.** Not named on the command line, and the purge refuses if it is not there. |

Nothing is deleted unless it is named with `--reference`. There is no flag that
selects duplicates automatically, and the scanner in section 5 cannot delete.

---

## 2. Why a plain `DELETE` on the audit will not do

Deleting the `audit_runs` row and letting the database cascade looks sufficient.
`audit_responses`, `audit_findings`, `external_audit_import_jobs` and
`external_audit_import_drafts` are all `ON DELETE CASCADE`.

It fails. `external_audit_records.audit_run_id` carries **no `ondelete` clause**, so
it is `NO ACTION`. On an imported audit — which is exactly what these are — the
cascade delete raises a foreign key violation and rolls back the whole transaction.

So the script deletes every row explicitly, children before parents, in an order
computed from the foreign keys reflected out of the database it is pointed at.

### Child inventory

Discovered by reflection and walked transitively, so a grandchild is found without
anyone listing it. `external_audit_records` hangs off the *import job*, not off the
audit run, and a one-level sweep would miss it.

| Table | Reaches audit via | `ON DELETE` | Disposition |
|---|---|---|---|
| `audit_responses` | `run_id` | CASCADE | purge |
| `audit_findings` | `run_id` | CASCADE | purge |
| `audit_finding_risks` | `audit_finding_id` | CASCADE | purge — junction only; the risk survives |
| `external_audit_import_jobs` | `audit_run_id` | CASCADE | purge |
| `external_audit_import_drafts` | `import_job_id`, `audit_run_id`, `promoted_finding_id` | CASCADE / NO ACTION | purge |
| `external_audit_records` | `audit_run_id`, `import_job_id` | **NO ACTION** | purge — blocks otherwise |
| `job_cell_links` | `audit_run_id`, `audit_finding_id` | SET NULL | **detach** — job data survives, link clears |

Foreign keys are only half of it. These tables reference records by a type name and
an id with no constraint behind them, so a delete neither cascades nor fails — it
just leaves them pointing at nothing:

| Table | Matched on | Disposition |
|---|---|---|
| `notifications` | `entity_type`/`entity_id` | purge — delivery artefact, would 404 |
| `assignments` | `entity_type`/`entity_id` | purge — work allocation on a record that will not exist |
| `audit_log_entries` | `entity_type`/`entity_id` | **retain** — see section 3 |
| `ai_decision_logs` | `entity_type`/`entity_id` | **retain** — account of an automated decision |
| `capa_actions` | `source_type`/`source_id` | **refuse** — see section 4 |
| `compliance_evidence_links` | `entity_type`/`entity_id` | **refuse** — changes a compliance claim |
| `job_cell_links` | `entity_type`/`entity_id` (`kind="app"`) | **refuse** — no `ON DELETE` to clear this one |

Any *other* table found referencing the purge set stops the script until somebody
classifies it. That is deliberate: sweeping it would destroy records nobody
reviewed, and ignoring it would leave dangling references, so neither is an
acceptable default.

---

## 3. The audit trail is written, not tidied

`audit_log_entries` is an append-only hash chain — each entry's `entry_hash` is
computed over the one before it. Deleting the entries about a purged audit would
break verification for every entry written afterwards and destroy the only evidence
that the audit existed. Those rows are meant to outlive their subject.

So the purge **appends** an entry (`action=delete`, `entity_type=audit_run`) carrying
the full pre-delete contents of the audit rows, **in the same transaction as the
deletes**. If the trail cannot be written, nothing is deleted.

---

## 4. Before you run: things that will stop it

Each of these is a refusal, not a warning. Resolve it, then re-run the dry run.

1. **A reference that does not exist.** A typo and an already-purged reference look
   identical from inside the script, so it refuses rather than reporting "all clear".
2. **A reference belonging to another tenant.** `reference_number` is globally
   unique, so being pointed at the wrong database resolves it perfectly to the wrong
   record. `--tenant-id` is asserted and checked.
3. **No survivor.** If nothing sharing the audit's identity would remain, this is not
   deduplication. Override: `--allow-no-survivor`.
4. **A CAPA raised from a doomed finding.** Corrective actions have their own
   reference numbers, owners and verification history, and the reference may already
   be in an external auditor's notes. Withdraw or repoint it at the surviving audit
   first — through the CAPA process, not this script.
5. **Compliance evidence links, or a `kind="app"` job cell link.** Repoint at the
   survivor or remove deliberately.
6. **Reference-number reuse or collision.** `ReferenceNumberService` mints
   `max(MAX(suffix), COUNT(*)) + 1`, so deleting rows can only lower the next value.
   `AUD-2026-0048` is likely the highest audit reference for 2026; the same applies to
   the `FND` and `AIM` sequences of the findings and import jobs being deleted. Read
   the `reference_arithmetic` block — it shows the sum both ways — then override with
   `--accept-reference-reuse-risk` only with a named human's acceptance.
   - `REISSUE` — a future genuine record carries a reference already used. Quiet.
   - `COLLISION` — the reference columns are UNIQUE, so the next insert **fails**.
     Nobody can raise an audit or a finding. Do not accept this one without a plan.

---

## 5. Procedure

Take a maintenance window. The trail append is serialised with a PostgreSQL advisory
lock, but the reference-number arithmetic assumes the register is not moving under it.

### Step 1 — scan for duplicates (read-only, safe any time)

```bash
env DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB' \
  python -m scripts.ops.run027.inventory_duplicate_registers \
  --tenant-id 1 --json | tee /tmp/dedup-scan.json
```

Read `registers_skipped` first. "No duplicates found" and "not looked at" are
different answers, and this is where they are told apart. On an audit group,
`import_derived` counts members that have an import job: all members import-derived is
the signature of a re-imported report; none is more likely two genuine audits sharing
a name.

This script has no `--apply` and cannot modify anything.

### Step 2 — dry run the purge

```bash
env DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB' \
  python -m scripts.ops.run027.purge_duplicate_audit_runs \
  --tenant-id 1 \
  --reference AUD-2026-0043 \
  --reference AUD-2026-0048 \
  --json --manifest /tmp/dedup-audit-twins-manifest.json \
  | tee /tmp/dedup-dryrun.json
```

Exit code `1` means a clean dry run; `3` means it refused. Check, in order:

- `blockers` — empty.
- `duplicate_group_survivors` — every entry names the surviving reference.
- `rows_per_table` and `deletion_order` — children before parents, `audit_runs` last.
- `soft_references` — nothing marked `refuse`.
- `rows_set_to_null_outside_purge` — job cell links you accept clearing.
- `collateral_risks` — risks escalated from a doomed finding. The link goes, the risk
  stays. If the risk is itself a duplicate, withdraw it separately afterwards.
- `reference_arithmetic` — every verdict `safe`.

Attach `/tmp/dedup-dryrun.json` and the manifest to the change record.

### Step 3 — apply

Only after the dry run is clean and a named human has approved it.

```bash
env DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB' APP_ENV=production \
  python -m scripts.ops.run027.purge_duplicate_audit_runs \
  --tenant-id 1 \
  --reference AUD-2026-0043 \
  --reference AUD-2026-0048 \
  --apply --i-understand-prod \
  --actor-email david.harris@plantexpand.com \
  --manifest /tmp/dedup-audit-twins-manifest.json \
  --json | tee /tmp/dedup-apply.json
```

`--manifest` is mandatory with `--apply`: it captures every column of every row
before deletion, and it is the only remaining record of what was destroyed.

Exit code `0` and `"outcome": "applied"` is success. Everything happens in one
transaction — deletes, soft-reference cleanup, and the trail entry — so a failure
leaves the register exactly as it was.

### Step 4 — verify

```bash
# 1. Re-running now refuses, because the references no longer exist. Expect 3.
env DATABASE_URL='...' python -m scripts.ops.run027.purge_duplicate_audit_runs \
  --tenant-id 1 --reference AUD-2026-0043 --reference AUD-2026-0048 --json; echo "exit=$?"

# 2. The register shows the audit once.
psql "$PGURL" -c "SELECT reference_number, status, score_percentage, created_at
                  FROM audit_runs
                  WHERE tenant_id = 1
                    AND title = 'B2 Audit - 2026-02-20T00:00:00 - Kevin Game'
                  ORDER BY created_at;"

# 3. Nothing orphaned survived.
psql "$PGURL" -c "SELECT 'records' AS t, COUNT(*) FROM external_audit_records WHERE audit_run_id IN (43, 48)
                  UNION ALL SELECT 'jobs', COUNT(*) FROM external_audit_import_jobs WHERE audit_run_id IN (43, 48)
                  UNION ALL SELECT 'findings', COUNT(*) FROM audit_findings WHERE run_id IN (43, 48)
                  UNION ALL SELECT 'responses', COUNT(*) FROM audit_responses WHERE run_id IN (43, 48);"

# 4. The purge is on the trail, and the chain still verifies.
psql "$PGURL" -c "SELECT sequence, action, entity_type, entity_id, user_email
                  FROM audit_log_entries WHERE tenant_id = 1
                  ORDER BY sequence DESC LIMIT 3;"
```

Then confirm the Audit Status screen for Plantexpand Limited shows one B2 audit at
97.7%, and check the audit trail verification endpoint reports the chain valid.

---

## 6. Rollback

There is none. This is a hard delete, which is the requirement.

Recovery is a point-in-time restore of the database to just before the apply, or
manual reconstruction from the manifest — which is why `--manifest` is mandatory and
why the dry run must be read rather than skimmed. Confirm the backup or PITR window
covers the change before running step 3.

---

## 7. Other duplicates

Groups from step 1 are **candidates for human review, not a work queue.** Two
inspections of the same yard on the same day by the same auditor may be a double
import or a morning and an afternoon visit, and nothing in the database
distinguishes them.

Once a group has been reviewed and a decision recorded, remove the agreed duplicates
by naming each reference explicitly, exactly as in steps 2 and 3. Registers other
than `audit_runs` have no purge script: the closure, dispositions and reference
arithmetic here were reviewed for audits only, and pointing this script at a
complaint would be acting on an approval nobody gave.
