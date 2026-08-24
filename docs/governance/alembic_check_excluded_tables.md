# Alembic check excluded tables

Owner: Platform / DBA (schema truth) with domain owners below.

This document inventories every table name in `_ALEMBIC_CHECK_EXCLUDED_TABLES`
in [`alembic/env.py`](../../alembic/env.py). Those names are omitted from
`alembic check` / autogenerate compare via `include_object` until additive
migrations (or model alignment) land.

**The register has been empty since 2026-09-12.** `alembic check` now compares
every table in `Base.metadata` against every table in the migrated schema, with
no name removed from the comparison. This document is therefore mostly the
history of how it got there, plus the rules that keep it empty.

**Do not remove an exclusion without a migration or model fix that makes
`alembic check` green without the name in the frozenset.** And do not add one
without reading "Scope of an exclusion" below: an entry mutes the whole table,
columns included, not just the operation that prompted it.

## Why exclusions existed

Every category this register ever carried has now been retired rather than
deferred again, each with a dated section at the foot of this document.

| Category | Reason it was deferred | Retired |
| --- | --- | --- |
| Legacy singular ISO27001 / ISMS names | In neither the metadata nor the schema, so nothing to defer. | 2026-07-29 |
| Retained model after drop | Model declared a table a migration had dropped. | 2026-07-29 |
| Missing create coverage | Model declared a table no migration created. | 2026-09-06 / 2026-09-07 |
| Plural ORM names | Table and model disagreed about columns. | 2026-09-08 / 2026-09-09 |
| Junction / config without models | Tables existed in PostgreSQL with no SQLAlchemy model, so compare offered to drop them. | 2026-09-12 |
| ORM vs migrated name mismatch | Model table name differed from the live migrated table. | 2026-09-12 |

Two of those retirements are worth restating as rules, because they are the ones
that were argued rather than obvious. Retaining a model whose table is gone is
not a deferral this register should accept again — the model cannot be queried,
and the one that existed broke `configure_mappers()` for every mapper in the
registry. Neither is a table with no model: an exclusion made the six junction
tables of 2026-09-12 invisible for six months while the code they were built to
replace went on reading the columns they were built to retire.

CI sets `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` so `process_revision_directives`
can strip noisy FK / index / unique / column ops. Phase 2 trialled surfacing unique
`DropConstraintOp` drift, but CI found 19 unique-constraint removals; suppression remains
until model/migration alignment lands. `AddColumnOp` / `AlterColumnOp` remain deferred
because ORM vs migrated column shapes still differ widely. CI now publishes the
`alembic-drift-inventory` artifact, which lists autogenerate operations before and after
filtering for every check attempt and is the safe incremental Phase 2 step.

## Inventory

Empty. No table is excluded from `alembic check`.

When the register is next non-empty, this section is a table with one row per
name and the columns `Table name | Owner | Reason`, where the table name is in
backticks. `scripts/validate_alembic_drift_ratchet.py` reads exactly that shape
out of this file and fails if it disagrees with `alembic/env.py` in either
direction — an undocumented exclusion, or a row for a table that is not
excluded. Nothing else in this document may use a backticked snake_case name in
a table's first column, because the parser cannot tell that apart from an
inventory row.

## Scope of an exclusion: intended table-level, actually total

An entry here is *intended* to defer **table-level** autogenerate compare for that
name. It is not a statement that anything about the table is acceptable.

Mechanically, though, it is not table-level at all. `include_object` returning
`False` removes the table from the comparison before column comparison happens, so
`alembic check` cannot report a column a model declares that the physical table
lacks on any excluded table. Measured, on the register as it stood until
2026-09-08: `soa_control_entries` declared four columns the migrated database did
not have (`implementation_method`, `justification`, `risk_treatment_reference`,
`tenant_id`), and the published drift inventory contained zero `AddColumnOp` —
because the table was on this list, not because the columns were there. That case
is closed (see the dated section below); the mechanism it demonstrates is not, and
is why `scripts/validate_alembic_drift_ratchet.py --database-url ...` runs a
second, unfiltered comparison to put a number on what this list hides, and why
`scripts/ops/run026/audit_attribution_schema.py` reports it per column.

Run026 found that distinction being lost. `scripts/ops/run025/verify_model_schema_parity.py`
filters its column comparison by this frozenset, so declared-but-absent columns on
these ~40 tables were not deferred, they were unreported — the difference between
15 findings and 19. Tools that ask column-level questions should not filter by this
list; `scripts/ops/run026/audit_attribution_schema.py` does not, and reports each
finding's exclusion status as a field instead of dropping it.

With the register empty that filter now narrows nothing, so the difference is
currently unobservable. It is still the wrong shape, and it will start hiding
findings again the first time a name is added, which is why the rule stays
written down rather than being treated as closed by the register being empty.

See [`attribution_schema_drift.md`](./attribution_schema_drift.md).

## How much is actually suppressed, and what stops it growing

Two separate mutes were in play. Only one of them is left, and it was never this
list:

| Mute | Mechanism | Measured on main (2026-07-29) | After 2026-09-09 | After 2026-09-12 |
| --- | --- | --- | --- | --- |
| Operation-type filter | `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` strips seven op types in `_filter_upgrade_ops` | 1058 operations across 209 tables reduced to 0 | unchanged | 1056 operations across 209 tables reduced to 0 |
| Table exclusion (this list) | `include_object` drops the table from the comparison entirely | 25 tables carrying 196 further operations, including 4 `AddColumnOp` | 8 tables carrying 23 operations, **0** `AddColumnOp` | **nothing** |

The op-type filter, not this list, is what makes the gate green, and it is now the
only thing muting it. That is the remaining work, and it is a much larger job
than this register was: 1056 operations, 431 of them `AlterColumnOp` and 248
`CreateIndexOp`, spread over 209 tables. What clearing this register bought is
that those 1056 are now the whole of the deferral — there is no second number
behind them, and no table whose drift is unmeasured.

Both numbers are printed by `alembic check` itself and enforced by
`scripts/validate_alembic_drift_ratchet.py`, which fails CI when:

- any `AddColumnOp` appears on a non-excluded table (zero tolerance — the count is
  0, and one absent declared column makes a whole table unreadable to a
  whole-entity ORM load);
- a table acquires drift, or an operation type, or a higher count than
  `alembic_drift_baseline.json` records;
- an excluded table's drift grows above its baseline;
- a name is in `_ALEMBIC_CHECK_EXCLUDED_TABLES` with no row in this document, or a
  row here names a table that is not excluded.

Drift *shrinking* is reported as a warning, not a failure, so that landing a
migration is never punished with a red gate. Refresh the baseline in the same PR.

## Maintenance

1. When adding a name to `_ALEMBIC_CHECK_EXCLUDED_TABLES`, add a row here in the same PR (owner + reason). This is enforced by `scripts/validate_alembic_drift_ratchet.py`.
2. When removing a name, delete the row and cite the migration / model PR that made compare safe.
3. Prefer shrinking this list via migrations over widening CI op filters.
4. Do not filter a column-level check by this list. See the section above.
5. `alembic check` alone cannot tell you whether an entry is still needed, because an excluded table produces no operations by construction. Run `scripts/validate_alembic_drift_ratchet.py --database-url ...` against a migrated database; it lists the entries with no drift left.

## Related

- Filter hook: `process_revision_directives` / `_filter_upgrade_ops` in `alembic/env.py`
- CI: `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1` around `alembic check` in `.github/workflows/ci.yml`


## 2026-07-11 create + unfilter

Added `20260711_ctl_docs_create` so fresh migrate materializes `controlled_documents`
and `controlled_document_versions` (previously only TEN2/RLS migrations assumed they
existed). Removed both names from `_ALEMBIC_CHECK_EXCLUDED_TABLES` so alembic check
covers them. Child document-control tables remain excluded until create coverage lands.

## 2026-07-29 eight stale entries removed

Removed the whole "Legacy singular ISO27001 / ISMS names" group:
`access_control_record`, `business_continuity_plan`, `information_asset`,
`information_security_risk`, `iso27001_control`, `security_incident`,
`soa_control_entry`, `supplier_security_assessment`.

No migration was needed, because there was nothing to defer. Each of these names is
in neither `Base.metadata` nor the migrated schema — the migrations that created the
singular tables were superseded by the plural ones, and a name that exists on
neither side of the comparison generates no operation whether it is excluded or not.
Measured by running `alembic.autogenerate.produce_migrations` against a database
built by `alembic upgrade head` with `include_object` allowing everything: all eight
produced zero operations of any type, on both PostgreSQL 14.20 and 16.14. `alembic
check` stays green with them gone, and `before_filter` is unchanged at 1060
operations.

The plural counterparts (`information_assets`, `security_incidents`,
`soa_control_entries`, `supplier_security_assessments`, `iso27001_controls`,
`access_control_records`, `business_continuity_plans`) do carry real drift and stay.

## 2026-07-29 `root_cause_analyses` removed with its model (C-14)

Removed the last "retained model after drop" entry. The exclusion existed only to
hide the `CreateTableOp` that `src/domain/models/rta_analysis.py` generated by
declaring a table migration `20260105_220237` had dropped. Rather than defer that
compare noise indefinitely, the model itself was deleted, so the name is now in
neither `Base.metadata` nor the migrated schema and generates no operation whether
it is excluded or not — the same argument as the eight entries above.

The model was not merely unused. It declared
`relationship("Incident", back_populates="rtas")` against an `Incident` that has no
`rtas` property, so importing it and calling `configure_mappers()` raised
`InvalidRequestError: Mapper 'Mapper[Incident(incidents)]' has no property 'rtas'`
for **every** mapper in the registry, not just its own. `alembic check` never hit it
because it does not configure mappers; a metadata-reading tool hits it immediately.

Measured on PostgreSQL 14.20 against a database built by `alembic upgrade head`:
`before_filter` unchanged at 1060 operations across 209 tables, `alembic check`
still green, and the drift hidden by `include_object` falls from 216 operations
across 33 tables to 212 across 32 — the 4 removed being the
`CreateTableOp` + 3 `CreateIndexOp` the dead model was generating for itself.
`docs/governance/alembic_drift_baseline.json` was regenerated with
`scripts/validate_alembic_drift_ratchet.py --write-baseline --database-url ...`;
the only change is the removal of those two `root_cause_analyses` entries.

## 2026-09-06 the Documents cluster migrated and unfiltered (C-24)

Removed the whole "Documents" owner group in one PR: `document_access_logs`,
`document_approval_actions`, `document_approval_instances`,
`document_approval_workflows`, `document_distributions`,
`document_training_links`, `obsolete_document_records`.

Unlike the eight names removed on 2026-07-29, these were not stale. Each one was
declared by `src/domain/models/document_control.py`, absent from every
Alembic-built schema, and — for six of the seven — read by
`src/api/routes/document_control.py`, which is why the endpoints above them had
to be taught to disclose the absence
([`docs/ops/absent-table-disclosure.md`](../ops/absent-table-disclosure.md)). The
deferral was real, so removing it needed a migration:
`20260906_doc_ctl_children` creates all seven, shaped from
`alembic.autogenerate` against a database at the previous head so that compare
produces nothing for them.

Measured on PostgreSQL 14.20 against a database built by `alembic upgrade head`:
`before_filter` is unchanged at 1058 operations across 209 tables — the seven
tables joined the comparison and contributed zero operations, which is the point
— and the drift hidden by `include_object` falls from 212 operations across 32
tables to 196 across 25. `alembic check` stays green with the seven names gone
from the frozenset.

The entries were deleted from `excluded_table_drift` and `excluded_tables` in
`alembic_drift_baseline.json` rather than the whole file being regenerated. A
full `--write-baseline` would also have tightened `complaints` and `incidents`
from 4 `DropColumnOp` to 3, which this work did not cause and did not measure on
the PostgreSQL 16 that CI runs; that pre-existing staleness is still reported as
a warning on every run, on main as well as here.

Row-level security was deliberately not extended to these tables. The three
document tables under FORCE RLS got there through a dedicated expand migration
plus a matching entry in `RLS_TABLES`
(`src/infrastructure/middleware/tenant_context.py`), and
`tests/integration/test_run026_rls_least_privilege_postgres.py` fails on a policy
that is not registered there and on a registration with no policy. Two of the
seven (`document_access_logs`, `obsolete_document_records`) declare `tenant_id`
`NOT NULL` and so meet the TEN2 precondition the expand waves used; they are the
obvious next candidates, and creating them here does not decide it.

## 2026-09-07 the IMS unification tables migrated and unfiltered (C-24)

Removed seven more: `ims_controls`, `ims_control_requirement_mappings`,
`ims_objectives`, `ims_process_maps`, `management_reviews`,
`management_review_inputs`, and `unified_audit_plans`.

These were the seven names on this register whose deferred drift was a whole
`CreateTableOp` — the table did not exist, so nothing else about it could be
compared. `20260907_ims_unification` creates all seven, shaped from
`alembic.autogenerate` against a database at the previous head.
`ims_requirements` and `cross_standard_mappings`, declared in the same model
file, already had a create migration (`f6e5d4c3b2a1`, 2026-04-07) and stay on
this register for column drift, which is a different problem with a different
fix.

`unified_audit_plans` is included despite its Risk / Audit owner because its
deferred drift was the identical shape — one `CreateTableOp`, one
`CreateIndexOp`, no reader, foreign keys only to `tenants` and `users` — and it
is declared in `src/domain/models/ims_unification.py` alongside the other six.
Splitting it out would have left one table absent for no reason other than the
owner column.

Measured on PostgreSQL 14.20 against a database built by `alembic upgrade head`:
`before_filter` is unchanged at 1058 operations across 209 tables — the seven
tables joined the comparison and contributed zero operations, and no other
table's per-table counts moved either — and the drift hidden by `include_object`
falls from 196 operations across 25 tables to 182 across 18. `alembic check`
stays green with the seven names gone from the frozenset, and the ratchet
reports `exclusions with no drift left (removable): []`.

As on 2026-09-06, the entries were deleted from `excluded_table_drift` and
`excluded_tables` in `alembic_drift_baseline.json` rather than the whole file
being regenerated, for the same reason: a full `--write-baseline` would also
tighten `complaints` and `incidents` from 4 `DropColumnOp` to 3, which this work
did not cause and did not measure on the PostgreSQL 16 that CI runs.

Not attempted here: the eight IMS / ISO27001 entries that remain, carrying 155 of
the 182 hidden operations between them. Those tables exist in the migrated schema
and disagree with their models about columns — `soa_control_entries` declares four
the database does not have, and seven of the eight have columns the database has
and the model does not, which autogenerate renders as `DropColumnOp` over live
compliance data. Settling them needs a domain decision about which side is
authoritative, not a create migration, so they are deferred with their
measurements to issue #1526 rather than guessed at here.

What this closes beyond the register: `DECLARED_BUT_UNMIGRATED` in
`tests/integration/_alembic_only_schema.py` is now empty, so the migration chain
builds every table the application declares. The assertion that pins it is
`test_the_measured_count_is_the_declared_count`, which compares the whole of
`Base.metadata` against an Alembic-built database and no longer has a list of
permitted absences to subtract first.

Row-level security was again deliberately not extended. All seven declare
`tenant_id` nullable, so unlike two of the document-control children they do not
even meet the TEN2 precondition the expand waves used.

## 2026-09-08 `soa_control_entries` converged and unfiltered (C-24, #1526)

Removed one name, and it is the one this document has been using as its worked
example of what a table-level exclusion hides. `soa_control_entries` was the
only table on the register — and, per the ratchet, the only table anywhere —
carrying `AddColumnOp`: the model declared `tenant_id`, `justification`,
`implementation_method` and `risk_treatment_reference`, and the migrated table
had none of them, so `select(SoAControlEntry)` raised `UndefinedColumn`. No gate
said so, because `include_object` had already dropped the table.

Unlike 2026-09-06 and 2026-09-07, this was not a create. The table exists and
holds a different design from the model, which is why 2026-09-07 handed it to
#1526 instead of guessing. The model's single `justification` faced the
database's `inclusion_justification` plus `exclusion_justification`; the model's
`implementation_method` faced the database's `implementation_description`; the
model additionally declared `risk_treatment_reference` and `tenant_id`, which the
database did not have; and the database additionally held `responsible_party`,
`target_completion_date` and `updated_at`, which the model did not declare. The
side-by-side table is in
[`attribution_schema_drift.md`](./attribution_schema_drift.md) — it is not
repeated here, because this file is parsed for its inventory rows and a
two-column table of backticked names reads as four more exclusions.

The decision recorded here is that **the database is authoritative for the live
compliance columns**, so the convergence is additive in both directions and
drops nothing: `20260908_soa_align` adds the four columns the model declared,
and `SoAControlEntry` absorbs the six the database had. `justification` and
`implementation_method` therefore arrive empty *beside* the columns they might
have meant. That is the point — which of the two justifications the single model
column means is an IMS decision about real certification evidence, and copying
either one into it would file an exclusion rationale as an inclusion rationale
or the reverse. Autogenerate would have rendered the same disagreement as six
`DropColumnOp` over that evidence.

Two smaller alignments were needed to reach zero: `implementation_status` is
widened from `varchar(30)` to the model's `varchar(50)` (a catalogue-only change
in PostgreSQL that cannot lose or reject a value, where narrowing the model
could), and the model now declares the `ON DELETE CASCADE` that the physical
`control_id` foreign key has always had, rather than the migration dropping and
recreating a live constraint to match a model that never described it.

Measured on PostgreSQL 16.14 against a database built by `alembic upgrade head`:
`before_filter` is unchanged at **1058 operations across 209 tables** — the table
joined the comparison and contributed zero, which is the point — and the drift
hidden by `include_object` falls from **182 operations across 18 tables to 167
across 17**, with `AddColumnOp` going from 4 to **0** across the whole
repository, excluded tables included. `alembic check` stays green with the name
gone from the frozenset, and the ratchet reports `exclusions with no drift left
(removable): []`.

As before, the entries were deleted from `excluded_table_drift` and
`excluded_tables` in `alembic_drift_baseline.json` rather than the whole file
being regenerated, for the same reason: a full `--write-baseline` would also
tighten `complaints` and `incidents` from 4 `DropColumnOp` to 3, which this work
did not cause. (That pre-existing staleness is now confirmed to be a
PostgreSQL 16 result, since this measurement was taken on 16.14 and reproduces
it; it is still not this PR's to fix.)

What this closes beyond the register: `DEFERRED_ABSENT_COLUMNS` in
`scripts/ops/run026/audit_attribution_schema.py` is now empty, so no
declared-but-absent column anywhere is deferred, and
`tests/unit/test_run026_deferral_register.py` pins the register at empty.

Row-level security was again deliberately not extended, and again the
precondition is not met: `tenant_id` arrives nullable because that is what the
model declares. It is also not backfilled — there is no parent row to derive a
tenant from that is not itself untenanted.

Still not attempted: the nine remaining IMS / ISO27001 entries, which carry 144
of the 167 hidden operations between them (the eight junction / config entries
hold the other 23). None of the nine is query-breaking any more — their column
drift is entirely the reverse direction, 50 `DropColumnOp` for columns the
database has and the model does not, plus 49 `AlterColumnOp` for shapes that
disagree. The same absorb-into-the-model treatment applies, one owner decision
per table. #1526.

## 2026-09-09 the last nine IMS / ISO27001 entries converged and unfiltered (C-24, #1526)

Removed `access_control_records`, `business_continuity_plans`,
`cross_standard_mappings`, `ims_requirements`, `information_assets`,
`information_security_risks`, `iso27001_controls`, `security_incidents` and
`supplier_security_assessments` — the whole of what the section above deferred,
and with it the "plural ORM names" category. Every name left on this register
is now a table with no model or a model whose table is called something else.

Unlike `soa_control_entries`, none of these nine was query-breaking: the models
declared no column the database lacked, `select(Model)` worked, and the
endpoints in `src/api/routes/iso27001.py` above them are live. What the
exclusion hid was the reverse — **50 columns of real ISO 27001 evidence that no
model could see**, which autogenerate renders as `DropColumnOp` over that
evidence, plus 49 shape disagreements, 16 foreign keys, 14 indexes and a unique
constraint.

The rule applied is the one 2026-09-08 used: *the side that moves is the side
whose move cannot lose or reject data.* That put almost all of the movement on
the models.

- **50 database-only columns** — the models absorbed them in the shape the
  database has, including the `NOT NULL` and server default on the six that
  carry one. Six sit beside a later column that might have been meant to
  replace them (`plan_name`/`name`, `plan_type`, `status`,
  `resource_name`/`system_name`, `findings`/`findings_details`,
  `notification_required`/`regulatory_notification_required`).
  `20260407_iso27001_drift_02` added the later one *beside* the original
  instead of migrating the data across, so both are kept. Which supersedes
  which is an IMS decision about live certification evidence and this PR does
  not make it (#1398).
- **25 nullability disagreements** (model `NOT NULL`, database nullable) — the
  models moved. `20260407_iso27001_drift_02` made these columns nullable
  deliberately, recording in its own docstring that existing rows could not
  satisfy `NOT NULL` and that the application supplies the value on new rows.
  Enforcing the model's claim now would need a value invented for every
  historic `granted_date`, `effective_date`, `scope` and `category`. The
  requirement is not lost — it is enforced where it always actually was, in the
  request schemas (`AccessControlCreate.granted_date`, `BCPCreate.scope`, …),
  and the read paths already null-guard these fields. Enforcing any of them in
  the database is a per-column expand exercise with the IMS owner, still #1526.
- **8 `jsonb` columns typed `JSON`** — the models moved, to the
  `JSON().with_variant(JSONB, "postgresql")` idiom `governed_knowledge.py`
  already uses. Converting the database to `json` would rewrite every table and
  give up containment operators and GIN indexing.
- **16 `varchar` columns narrower in the database than in the model** — the
  *database* moved, and this is the only place it did. It is the
  `implementation_status` argument from 2026-09-08 applied fifteen more times:
  widening a `varchar` in PostgreSQL is catalogue-only, cannot reject or
  truncate a value, and it closes a live failure — a 150-character
  `threat_source` passes the request schema today and is rejected by
  `varchar(100)` with a 500.
- **16 foreign keys** — nine differed only in `ON DELETE`, which the database
  has as `SET NULL` and the models did not declare; the models now declare it.
  The other seven were absent from the database and `20260909_iso_absorb`
  creates them, also `SET NULL`. `SET NULL` rather than the model's silent
  `NO ACTION` on purpose: these are `owner_id` / `reported_by_id` columns, all
  nullable, each with a `_name` column beside it holding the recorded name, and
  `NO ACTION` would turn deleting a user into a foreign-key violation. The
  migration **refuses** rather than repair if any of the seven columns holds a
  dangling id (`OrphanedReferenceError`) — nulling it would discard the only
  machine-readable link that row has to a person, and creating the constraint
  `NOT VALID` would reflect as a real foreign key, so the next `alembic check`
  would call the drift resolved when it is not.
- **14 indexes and 1 unique constraint** — the models declare them. Nothing is
  created or dropped.
- **1 table comment** the model declared and the database lacked — set by the
  migration.

Measured on PostgreSQL 16.14 against a database built by `alembic upgrade head`:
`before_filter` is unchanged at **1058 operations across 209 tables** — the nine
tables joined the comparison and contributed zero between them, and no other
table's per-table counts moved — and the drift hidden by `include_object` falls
from **167 operations across 17 tables to 23 across 8**. `AddColumnOp` stays at
0 across the whole repository. `alembic check` is green with all nine names gone
from the frozenset, and the ratchet reports `exclusions with no drift left
(removable): []`.

As on the three preceding dates, the nine entries were deleted from
`excluded_table_drift` and `excluded_tables` in `alembic_drift_baseline.json`
rather than the whole file being regenerated, for the same reason: a full
`--write-baseline` would also tighten `complaints` and `incidents` from 4
`DropColumnOp` to 3, which this work did not cause.

Row-level security was again deliberately not extended: every `tenant_id` in
these nine is nullable, so none meets the TEN2 precondition the expand waves
used.

What is left on this register is eight names and 23 operations, and it is one
problem, not nine: seven junction / config tables that exist in PostgreSQL with
no model (rendered as `DropTableOp`), and `escalation_rules`, a model whose
table is called `escalation_rules_config` (rendered as `CreateTableOp`). None of
them is a column-shape question, so none of them is fixed by the treatment used
here.

## 2026-09-12 the last eight entries cleared and the register emptied (C-24, #1526)

Removed all eight, and with them the last two categories. There is no inventory
row left in this document and no name left in the frozenset.

The eight were two problems, and neither was a column-shape disagreement, so
neither was fixable by the absorb-into-the-model treatment the four preceding
dates used.

**Six junction tables nothing reads, dropped.**
`20260220_normalize_json` created six junction tables to replace JSON array
columns, copied the arrays into them, and renamed the source columns with a
`_legacy` suffix. The second half of that plan never happened. No SQLAlchemy
model was ever written for any of the six; no service, route or script names
them (verified by search across `src/`, `scripts/`, `frontend/src/` and `tests/`
— every apparent hit is the *plural* `risk_control_mappings`, which is a real
model in `risk_register.py` and a different table); and the application still
reads the `_legacy` columns the junctions were built to retire, through
`Risk.clause_ids_json_legacy` and the field maps in `audit_service.py`.

So their contents were a six-month-old derived copy of data whose source is still
present and still written to. Dropping them is not a data decision. The
migration counts the rows in each table and logs the count and the source column
before dropping it, so the deploy log is the record of what each environment
discarded rather than this paragraph; and `downgrade` recreates all six in their
original shape and re-derives their rows from the same `_legacy` columns with the
same SQL `20260220_normalize_json` used, which is what makes it reversible.

Renaming them into a finished normalized design was the alternative, and it is
not a migration: it needs models, a rewrite of the `_legacy` reads, and an API
contract change on `clause_ids` / `control_ids`. That work is
[`json-column-reduction.md`](../data/json-column-reduction.md) and it is
untouched here. What this settles is only that a half-finished normalization
should not hold a gate muted while it waits.

**One model that named a table which does not exist, pointed at the right one.**
`escalation_rules` and `escalation_rules_config` were two rows on this register
for one mismatch. `20260220_workflow_persist` created
`escalation_rules_config`; `EscalationRule` in `src/domain/models/workflow.py`
declared `escalation_rules`. The model was the wrong side, and not merely
differently named — `select(EscalationRule)` would have raised `UndefinedTable`
on every migrated database since February. Nothing raised, because nothing
queries it: the escalation logic in `workflow_service.py` uses an in-memory
`EscalationRule` `Enum` that happens to share the name. So the rename cannot
break a caller, and it makes `escalation_logs.rule_id` reference the table its
physical foreign key has always pointed at.

Three columns then had to converge for the table to compare to zero, and both
directions were used, by the 2026-09-08 rule — *the side that moves is the side
whose move cannot lose or reject data*:

- `tenant_id`, declared by the model and absent from the table, is added by
  `20260912_clear_junctions` with its foreign key and index. It had to be: this
  would otherwise have been the only `AddColumnOp` in the repository, the class
  the ratchet fails on unconditionally, and it would have made the table
  unreadable to `select(EscalationRule)` at the exact moment the rename made the
  class reachable.
- `trigger_unit`, `send_notification` and `is_active` are `NOT NULL` in the model
  and nullable-with-a-server-default in the table. Here the **database** moves.
  The server default already guarantees a value on every row inserted without
  one, so the only row `SET NOT NULL` could reject is one where a NULL was
  written explicitly — and nothing has ever written to this table. Any such row
  is repaired to the column's own server default first and the count logged, so
  the outcome does not depend on what the table holds. Making the model
  `Optional` instead would have shipped a nullable boolean flag on a table that
  is about to get its first reader.

Measured on PostgreSQL 16.14 against a database built by `alembic upgrade head`:
`before_filter` falls from **1058 operations across 209 tables to 1056 across
209**, and the drift hidden by `include_object` falls from **23 operations across
8 tables to nothing at all**. `AddColumnOp` stays at 0. `alembic check` is green
with the frozenset empty, and the ratchet reports `tables removed from the
comparison entirely by include_object: 0`.

The two-operation fall is on `escalation_logs`, not on the eight: its `rule_id`
foreign key was being reported as one `CreateForeignKeyOp` (the model's, against
a table that did not exist) plus one `DropConstraintOp` (the database's, against
a table with no model), and the rename collapses both. `escalation_rules_config`
itself joins the comparison contributing zero, which is the point, and the six
junction tables leave it by being in neither metadata nor schema.

As on the four preceding dates, `alembic_drift_baseline.json` was edited rather
than regenerated with `--write-baseline`, and for the same reason: a full refresh
would also tighten `complaints` and `incidents` from 4 `DropColumnOp` to 3, which
this work did not cause. What changed is `excluded_tables` and
`excluded_table_drift`, which are now empty; `escalation_logs`, tightened to the
single `CreateForeignKeyOp` it has left, because that fall *is* this PR's; and
the three aggregates that have to move with it — `total_operations` 1060 → 1058,
`CreateForeignKeyOp` 103 → 102, `DropConstraintOp` 33 → 32. The aggregates are
not decoration:
`test_the_baseline_covers_every_table_it_claims_to` asserts that
`total_operations` equals the sum of the per-table counts, so a per-table
tightening that leaves them alone makes the file self-contradictory. It still
overstates reality by exactly the 2 `DropColumnOp` the preceding dates declined
to absorb, on both sides of that equality, which is the ceiling it is meant to be.

Row-level security was again deliberately not extended.
`escalation_rules_config.tenant_id` arrives nullable because that is what the
model declares, so the table does not meet the TEN2 precondition the expand waves
used, and there is no parent row to derive a tenant from.

Left as it was, deliberately: `escalation_logs.tenant_id` still has no foreign
key to `tenants` although the model declares one. It is one of the 102
`CreateForeignKeyOp` the operation-type filter suppresses repository-wide, it
predates this work, and fixing one instance of a repository-wide class here would
change no gate. It is recorded in the refreshed baseline.

What this closes beyond the register: nothing about a table is now deferred by
name anywhere in the repository. `DECLARED_BUT_UNMIGRATED` (2026-09-07),
`DEFERRED_ABSENT_COLUMNS` (2026-09-08) and this register (2026-09-12) are all
empty. The whole of the remaining deferral is the operation-type filter, it is
one number, and it is printed on every run.
