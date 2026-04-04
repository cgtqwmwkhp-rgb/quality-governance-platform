# Alembic Migration Squash Runbook

**Owner**: Platform Engineering  
**Target**: Q3 2026  
**Last updated**: 2026-04-03  
**Review cycle**: After each major schema release

---

## Current state

- The repository carries **80** revision files under `alembic/versions/` (see `alembic history` for the live chain; count verified `ls alembic/versions/*.py | wc -l`).
- Each environment applies revisions sequentially; long chains increase deploy time, review fatigue, and merge conflict risk.
- This runbook describes squashing that chain into a **single baseline** revision that matches the current ORM/metadata, then archiving historical files.

Squashing **does not** remove the need for normal Alembic discipline afterward: every schema change still ships as a new revision with upgrade (and downgrade when feasible).

---

## Preconditions

- [ ] Stakeholders agree on the **freeze window** (no parallel migration PRs).
- [ ] A **backup** of every database that consumes these migrations exists and has been restore-tested recently.
- [ ] `alembic heads` shows a **single** head (resolve branches first).
- [ ] CI green on `origin/main` with the revision chain you intend to squash.

---

## Step-by-step squash procedure

### 1. Freeze window

1. Announce the window in `#platform` (or equivalent): start time, expected duration, and “no new `alembic/versions` PRs until complete.”
2. Merge or close in-flight migration PRs; hold schema changes until the squash merges.
3. Tag the commit that will be the **last pre-squash** revision (e.g. `git tag pre-migration-squash-2026-q3`).

### 2. Backup

1. Take an **application-consistent** or **PITR-eligible** backup of production and staging databases per `docs/runbooks/database-recovery.md`.
2. Export a logical dump for at least one staging clone used for validation:

   ```bash
   pg_dump --no-owner --format=custom -f pre_squash_$(date +%Y%m%d).dump "$DATABASE_URL"
   ```

3. Record backup id, region, and retention in the change ticket.

### 3. Generate baseline (developer workstation or CI job)

Work from a clean tree on the branch that will receive the squash.

1. **Archive** existing files (do not delete yet — see step 5):

   ```bash
   mkdir -p alembic/versions/_archive_pre_squash_YYYYMMDD
   git mv alembic/versions/*.py alembic/versions/_archive_pre_squash_YYYYMMDD/
   ```

2. Ensure `alembic.ini` and `env.py` still point at the correct metadata and database URL for a **throwaway** local DB or empty schema.

3. Generate a new baseline from current models (adjust command flags to match project conventions):

   ```bash
   alembic revision --autogenerate -m "baseline_after_squash"
   ```

4. Edit the generated revision: remove noise, verify constraints and indexes match production, and add data migrations if autogenerate cannot express required one-off steps.

5. Set `down_revision = None` only if this revision is intended to **replace** the entire chain for **new** databases. For environments that already ran old revisions, you typically need a **merge** or **stamp** strategy (see Verification).

### 4. Verify

1. On a **fresh** database: `alembic upgrade head` — schema matches expectations (spot-check critical tables and enums).
2. On a **copy** of staging data restored from backup:
   - Either `alembic stamp <new_revision_id>` after manual confirmation that the live schema already equals the baseline, **or**
   - Run a controlled upgrade path documented in the ticket if intermediate steps are required.
3. Run the full test suite and migration smoke: `make pr-ready` (or project-equivalent).
4. Run application smoke: `/healthz`, `/readyz`, and one CRUD path per major module.

### 5. Archive old files

1. Keep `alembic/versions/_archive_pre_squash_*` in git **or** move to `docs/evidence/` with a pointer in the change ticket — choose one approach and document it in the PR.
2. Ensure `alembic history` in the PR shows a single linear baseline (or an explicit merge revision if multiple heads existed).

### 6. Test

1. CI: fresh DB `upgrade head` job must pass.
2. Staging: deploy from the PR branch; confirm `alembic_version` row matches the new revision id.
3. Regression: run API contract / integration tests that touch schema-bound features.

### 7. Update team docs

1. Update `docs/data/migration-guide.md` (or equivalent) with: new baseline revision id, stamp instructions for clones, and date of squash.
2. Add a short entry to the engineering changelog / release notes.
3. Remove the freeze notice; resume normal migration PR flow.

---

## Rollback if the squash fails

Use this section if verification fails **before** production promotion, or if production deploy surfaces a schema mismatch.

### Before production deploy

1. **Stop**: do not stamp production; revert the Git branch to the tag from step 1 (`pre-migration-squash-*`).
2. Restore `alembic/versions/` from `_archive_pre_squash_*` or `git revert` the squash commit.
3. Confirm `alembic heads` matches the pre-squash state.
4. Re-run CI and staging deploy from the reverted tree.

### After production deploy (schema wrong or app failing)

1. **Stop traffic** or enable read-only mode per `docs/runbooks/rollback.md` / deployment runbook.
2. **Restore database** from the backup taken in step 2 (PITR or logical restore) per `docs/runbooks/database-recovery.md`.
3. **Redeploy** the last known-good application image and migration set (the commit tagged pre-squash).
4. Post-incident: document root cause (autogenerate miss, stamp error, enum drift) before retrying the squash.

---

## Roles and communication

| Role | Responsibility |
|------|----------------|
| Platform Engineering | Owns schedule, baseline revision, stamp/upgrade strategy |
| SRE / On-call | Backup verification, production rollback execution |
| Product engineering | Freeze compliance, smoke tests after staging |

---

## References

- `alembic/env.py` — runtime configuration
- `docs/data/migration-guide.md` — team-facing migration practices
- `docs/runbooks/database-recovery.md` — backup and PITR
