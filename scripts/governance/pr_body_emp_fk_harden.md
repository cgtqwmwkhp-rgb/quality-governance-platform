# Change Ledger (CL-EMP-FK-HARDEN)

**Path claim:** `path11/emp-fk-harden`

## File allowlist (exclusive)

- `src/domain/models/engineer.py`
- `alembic/versions/20260726_engineer_user_fk_set_null.py`
- `tests/unit/test_engineer_user_fk_set_null.py`
- `scripts/governance/pr_body_emp_fk_harden.md`

**Out of scope:** EMP-UI roster/pickers, PAMS sync service, User delete APIs, frontend, dependabot.

## 1) Summary

- **Feature / Change name:** EMP-FK-HARDEN — Engineer.user_id ON DELETE SET NULL
- **User goal:** Deleting a QGP User login must not destroy the Engineer/PAMS person row; the login link clears (`user_id` → NULL) and the workforce person remains.
- **In scope:** Model FK ondelete, Alembic FK recreate, unit scaffold test, this ledger
- **Out of scope:** Soft-delete UX, re-link workflows, cascade changes on competency/tickets
- **Feature flag / kill switch:** N/A — schema FK semantics only; revert + downgrade restores CASCADE

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| `Engineer.user_id` ORM FK | `ON DELETE CASCADE` | `ON DELETE SET NULL` |
| DB FK `engineers.user_id` → `users.id` | Cascade deletes Engineer row | Sets `user_id` NULL; Engineer row kept |
| PAMS / unlinked employees | Cascade risk if linked then user deleted | Person row preserved as unlinked |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Same nullable unique column; only delete action changes
- **Breaking changes:** None for readers/writers; User DELETE no longer removes Engineer rows
- **Migration:** Drop existing user_id FK; recreate named `fk_engineers_user_id` with SET NULL
- **Rollback strategy:** Downgrade recreates FK with CASCADE; revert code

## 4) Acceptance Criteria (AC)

- [x] AC-01: Model `Engineer.user_id` uses `ForeignKey(..., ondelete="SET NULL")`
- [x] AC-02: Alembic revision chains from `20260725_eng_qgp_ov` and upgrades to SET NULL
- [x] AC-03: Downgrade restores CASCADE
- [x] AC-04: Unit test asserts model ondelete + migration scaffold

## 5) Testing Evidence

- [x] `pytest tests/unit/test_engineer_user_fk_set_null.py`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Linked Engineer survives User delete — `user_id` becomes NULL, person row remains
- [x] CUJ-02: Unlinked / PAMS-only Engineer unchanged by FK semantics
- [x] CUJ-03: Relink possible later — unique nullable `user_id` still allows a new User link

## 7) Observability & Ops

- No new logs/metrics; verify via Alembic upgrade on staging and spot-check Engineer count after a test User delete (staging only)

## 8) Release Plan

1. Merge after CI green
2. Run Alembic upgrade on staging (`20260726_emp_user_fk`)
3. Staging smoke: delete a non-prod test User linked to an Engineer → Engineer remains with `user_id` NULL

## 9) Rollback Plan

1. Revert squash commit
2. `alembic downgrade` restores CASCADE FK
3. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: Contracts (FK semantics documented; exclusive allowlist)
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [x] Gate 4: Canary (N/A ok)
- [x] Gate 5: Production verification plan ready

## Test plan

- [ ] `pytest tests/unit/test_engineer_user_fk_set_null.py`
- [ ] Staging: Alembic upgrade; confirm FK `fk_engineers_user_id` has `ON DELETE SET NULL`
- [ ] Staging: delete linked test User → Engineer row remains, `user_id` IS NULL
