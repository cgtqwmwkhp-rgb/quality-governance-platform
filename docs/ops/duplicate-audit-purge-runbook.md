# Runbook — purging duplicate audit runs (FR-DEDUP-01)

Hard-deletes a named duplicate audit and everything belonging to it, and scans the
audit, risk, action and case registers for other duplicates.

| | |
|---|---|
| Scripts | `scripts/ops/run027/purge_duplicate_audit_runs.py`, `scripts/ops/run027/inventory_duplicate_registers.py`, `scripts/ops/run027/_remediate.py` |
| Tests | `tests/unit/test_run027_duplicate_audit_purge.py` |
| Requires | Direct database access. **Not** wired into CI, deploy, or the conveyor. |
| Default | Dry run. `--apply` is opt-in and needs `--i-understand-prod` on production. |

> **This was not executed against production.** The environment the change was
> authored in has no `DATABASE_URL` and no route to the production database. The
> scripts, the refusals and the runbook below are the deliverable; an operator with
> database access performs the run. **Do not run `--apply` until the dry run is
> clean (exit 1) and a named human has approved it.**

---

## 1. What FR-DEDUP-01 authorises

Production holds duplicate Achilles 2026 Audit re-imports for Plantexpand Limited
(tenant 1). The PROD dry-run named these two for purge:

| Reference | Id | Status | Score | Disposition |
|---|---|---|---|---|
| `AUD-2026-0043` | 43 | `pending_review` | null | **Purge.** |
| `AUD-2026-0048` | 48 | `completed` | 99.0 | **Purge.** |
| earlier Achilles import (operator-named via `--survivor-reference`) | — | varies | varies | **Survives.** |

The original fixture narrative used a B2 audit at 97.7% `completed`. The PROD
dry-run that blocked apply showed Achilles UVDB with **diverging lifecycle
columns** (`status` / `score_percentage`), which is why 0048 alone fails the
identity-group survivor check — see blocker C below.

Nothing is deleted unless it is named with `--reference`. There is no flag that
selects duplicates automatically, and the scanner cannot delete.

---

## 1a. PROD dry-run blockers (exit 3) — resolve before apply

The governed dry-run completed and **refused apply**. Would-delete inventory was
250 rows (`audit_finding_risks` 44, `audit_findings` 97, `audit_runs` 2,
`external_audit_import_drafts` 103, `external_audit_import_jobs` 2,
`external_audit_records` 2). Three blockers stopped it:

### A — 970 `compliance_evidence_links` (must-not-touch)

Live links with `entity_type='audit_finding'` pointing at doomed findings. These
links are what make an ISO clause count as covered (or record a gap). Deleting
them changes the tenant's stated compliance position; leaving them dangling
overstates coverage with evidence that no longer exists.

**Clear with:** `--survivor-reference <SURVIVOR>` + `--remap-evidence-links` +
`--expect-evidence-links N` (N = live hit count from the dry run). Matching
survivor findings are chosen by title/description/finding_type/severity. Where
the survivor already covers the same `(clause_id, cover_kind)`, the doomed link
is **soft-deleted** (`deleted_at`) as `WITHDRAW_REDUNDANT`. Unmappable links
require `--withdraw-unmappable-evidence` or they refuse again.

### B — 10 `capa_actions` (ids 18, 60–68) (must-not-touch)

`source_type='audit_finding'` pointing at doomed findings. CAPAs are a governed
register with their own reference numbers, owners and verification history.

**Clear with:** `--survivor-reference <SURVIVOR>` + `--reassign-capa-to-survivor`
+ `--expect-capa-action ID` for **every** CAPA id (exact set match). This
updates `source_id` only — title, status, verification history and
`reference_number` are untouched.

**There is no CAPA withdraw in this script.** `CAPAStatus` has no `withdrawn`
value; faking `closed` or nulling `source_type` would corrupt the register. If a
CAPA must go away rather than be reassigned, withdraw it through the CAPA
process first, then re-run the dry run (it will no longer appear).

### C — `AUD-2026-0048` has no identity-group survivor

Audit identity includes `status` and `score_percentage`. 0048 is
`completed` @ 99 while its siblings are `pending_review` with null score, so
the group size for 0048 is 1. Using `--allow-no-survivor` would write "destroying
the only copy" into the trail, which is the wrong claim when an earlier twin
exists.

**Clear with:** `--survivor-reference <SURVIVOR_AUD_REF>`. That **authorises**
the survivor (exists, same tenant, not itself being purged) and **corroborates**
content identity ignoring lifecycle columns (`status`, `score_percentage`). The
scanner's default identity is unchanged — lifecycle columns stay in grouping for
duplicate review.

Confirm the survivor's `reference_number` and `created_at` against the scanner
output before naming it. A wrong but plausible survivor would receive 970
repointed evidence links.

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
| `capa_actions` | `source_type`/`source_id` | **refuse** by default; opt-in reassign — see §1a B |
| `compliance_evidence_links` | `entity_type`/`entity_id` | **refuse** by default; opt-in remap/withdraw — see §1a A |
| `job_cell_links` | `entity_type`/`entity_id` (`kind="app"`) | **refuse** — no remediation flag; clear by hand |

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
the full pre-delete contents of the audit rows **and** the remediation summary in
`new_values.remediation` (hash-covered), **in the same transaction as the
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
   deduplication. Prefer `--survivor-reference` (see §1a C). Override of last resort:
   `--allow-no-survivor` — does **not** rescue a bad/missing/cross-tenant
   `--survivor-reference`.
4. **A CAPA raised from a doomed finding.** Clear with `--reassign-capa-to-survivor`
   + exact `--expect-capa-action` list, or withdraw via the CAPA process first.
5. **Compliance evidence links.** Clear with `--remap-evidence-links` +
   `--expect-evidence-links N` (+ `--withdraw-unmappable-evidence` if needed).
   A `kind="app"` job cell link still refuses — clear by hand.
6. **Reference-number reuse or collision.** `ReferenceNumberService` mints
   `max(MAX(suffix), COUNT(*)) + 1`, so deleting rows can only lower the next value.
   Read the `reference_arithmetic` block, then override with
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

Read `registers_skipped` first. Pick the intended survivor reference from the
Achilles group and confirm it against Audit Status.

### Step 2 — dry run the purge (with remediation flags)

Replace `SURVIVOR_REF` with the confirmed survivor. Pass the live CEL count and
every CAPA id from the previous refused dry run (or the new dry run's
`soft_references` / remediation blockers).

```bash
env DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB' \
  python -m scripts.ops.run027.purge_duplicate_audit_runs \
  --tenant-id 1 \
  --reference AUD-2026-0043 \
  --reference AUD-2026-0048 \
  --survivor-reference SURVIVOR_REF \
  --remap-evidence-links --expect-evidence-links 970 \
  --withdraw-unmappable-evidence \
  --reassign-capa-to-survivor \
  --expect-capa-action 18 \
  --expect-capa-action 60 --expect-capa-action 61 --expect-capa-action 62 \
  --expect-capa-action 63 --expect-capa-action 64 --expect-capa-action 65 \
  --expect-capa-action 66 --expect-capa-action 67 --expect-capa-action 68 \
  --json --manifest /tmp/dedup-audit-twins-manifest.json \
  | tee /tmp/dedup-dryrun.json
```

Exit code `1` means a clean dry run; `3` means it refused. Check, in order:

- `blockers` — empty.
- `remediation` — finding matches, evidence dispositions (`REMAP` /
  `WITHDRAW_REDUNDANT` / `WITHDRAW_UNMAPPABLE`), CAPA reassigns.
- `duplicate_group_survivors` / `remediation.named_survivors` — intended survivor.
- `rows_per_table` and `deletion_order` — children before parents, `audit_runs` last.
- `soft_references` — CEL/CAPA still reported as `refuse` (disposition unchanged);
  blockers deferred only because remediation covers them.
- `collateral_risks` — risks escalated from a doomed finding. Link goes, risk stays.
- `reference_arithmetic` — every verdict `safe` (or accepted explicitly).

Attach `/tmp/dedup-dryrun.json` and the manifest to the change record. The
manifest's `remediation_pre_update_rows` holds CEL/CAPA rows before UPDATE — those
are reversible from the manifest; the deletes are not.

### Step 3 — apply

Only after the dry run is clean and a named human has approved it.

```bash
env DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB' APP_ENV=production \
  python -m scripts.ops.run027.purge_duplicate_audit_runs \
  --tenant-id 1 \
  --reference AUD-2026-0043 \
  --reference AUD-2026-0048 \
  --survivor-reference SURVIVOR_REF \
  --remap-evidence-links --expect-evidence-links 970 \
  --withdraw-unmappable-evidence \
  --reassign-capa-to-survivor \
  --expect-capa-action 18 \
  --expect-capa-action 60 --expect-capa-action 61 --expect-capa-action 62 \
  --expect-capa-action 63 --expect-capa-action 64 --expect-capa-action 65 \
  --expect-capa-action 66 --expect-capa-action 67 --expect-capa-action 68 \
  --apply --i-understand-prod \
  --actor-email david.harris@plantexpand.com \
  --manifest /tmp/dedup-audit-twins-manifest.json \
  --json | tee /tmp/dedup-apply.json
```

`--manifest` is mandatory with `--apply`. Order inside the transaction:
remediation UPDATEs → soft PURGE deletes → FK closure deletes → trail append →
verification queries → commit.

Exit code `0` and `"outcome": "applied"` is success.

### Step 4 — verify

```bash
# 1. Re-running now refuses, because the references no longer exist. Expect 3.
env DATABASE_URL='...' python -m scripts.ops.run027.purge_duplicate_audit_runs \
  --tenant-id 1 --reference AUD-2026-0043 --reference AUD-2026-0048 --json; echo "exit=$?"

# 2. No live CEL / CAPA still points at the purged finding ids.
psql "$PGURL" -c "SELECT COUNT(*) FROM compliance_evidence_links
                  WHERE entity_type = 'audit_finding'
                    AND entity_id IN (SELECT id::text FROM audit_findings WHERE run_id IN (43, 48))
                    AND deleted_at IS NULL;"
# (should be 0 — findings are gone too; also check known pre-purge finding id lists)

# 3. The register shows the audit once under the survivor reference.
psql "$PGURL" -c "SELECT reference_number, status, score_percentage, created_at
                  FROM audit_runs
                  WHERE tenant_id = 1
                    AND lower(title) LIKE '%achilles 2026%'
                  ORDER BY created_at;"

# 4. The purge is on the trail (new_values includes remediation), chain verifies.
psql "$PGURL" -c "SELECT sequence, action, entity_type, entity_id, user_email
                  FROM audit_log_entries WHERE tenant_id = 1
                  ORDER BY sequence DESC LIMIT 3;"
```

---

## 6. Rollback

There is none for the hard deletes. That is the requirement.

CEL remaps/withdrawals and CAPA reassignments **are** reversible from the
manifest's `remediation_pre_update_rows` (`id`, old `entity_id`/`source_id`, old
`deleted_at`). Recovery for deletes is PITR or reconstruction from the manifest.
Confirm the backup or PITR window covers the change before running step 3.

---

## 7. Other duplicates

Groups from step 1 are **candidates for human review, not a work queue.** Once a
group has been reviewed and a decision recorded, remove the agreed duplicates by
naming each reference explicitly, with `--survivor-reference` and remediation
flags as needed. Registers other than `audit_runs` have no purge script.
