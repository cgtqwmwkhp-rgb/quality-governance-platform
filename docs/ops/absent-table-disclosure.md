# Absent tables and the surfaces above them

**Owner:** Platform Engineering, with the domain owners named in
[`docs/governance/alembic_check_excluded_tables.md`](../governance/alembic_check_excluded_tables.md)
**Audience:** Testers, on-call, auditors, anyone deciding whether a failing screen is a defect
**Status:** Honesty lock — disclosure only. No feature in this document has been built.

Sixteen tables the SQLAlchemy models declare are not in the database, seven of
them confirmed absent in production. This document records which they are, how
each was measured and where, which user-facing surfaces read them, and what each
surface now says.

It exists because a tester without this list will log a schema absence as a
functional defect, and because the document-control endpoints above these tables
cannot have been working in production while every CI gate stayed green.

---

## 1. How this was measured, and in which environment

Read this section before quoting any number from this document. The two
measurements below do not cover the same ground, and the difference matters.

| Measurement | Environment | Covers | Method |
|---|---|---|---|
| Production read | **production** (`qgp_prod_live`, read-only) | the **7** document-control tables named below, and the count of 240 base tables | `information_schema` existence query, run and recorded in the Run 021 coverage measurement of 28 Jul 2026 |
| Local reproduction | **local PostgreSQL 14**, built by `alembic upgrade head` on an empty database | all **248** declared tables | `scripts/ops/run026/inventory_declared_vs_actual_tables.py`, artefact at [`docs/evidence/run026-local-alembic-head-absent-tables-20260728.json`](../evidence/run026-local-alembic-head-absent-tables-20260728.json) |

**What is a production fact:** the seven document-control tables are absent from
production. Those seven were enumerated in production directly, and they are the
only tables any change in this work depends on.

**What is not:** the figure of sixteen. Only the local build enumerated all 248
declared tables; the Run 021 work states sixteen but explicitly did not re-derive
the list, so the nine names beyond document control (§2) rest on the local
reproduction and on the deferral register, not on a recorded production read.
Nothing is disclosed on their behalf — none of them has a reader — so no
user-facing behaviour depends on that weaker evidence.

The local build is worth having anyway, because production's schema is built by
the same migrations: a table no migration creates is absent from any
Alembic-built deployment, which makes the finding reproducible by anyone with a
local Postgres and no production credentials. Where the two could still differ is
a table created out-of-band by hand — which is exactly why the seven that matter
were checked in production rather than inferred.

Locally: **248** tables declared, of which **232** are present and **16** absent;
the database holds **240** tables in total, the other **8** having no model
(`alembic_version`, four `risk_*_mapping` junctions, two audit clause-mapping
junctions, `escalation_rules_config`). Production also reports **240** base
tables, which is consistent with the same sixteen being absent there, but
consistency is not enumeration and is not claimed as such.

### Why the existing tools could not report this

- **`alembic check`** builds its comparison database by migrating an empty
  Postgres — so the models and that database agree by construction — and CI then
  strips the table and column operations via
  `ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1`.
- **Both CI harnesses** build their schema with `Base.metadata.create_all`. A
  table with no create migration is therefore present in every test database and
  in no deployment. A test can pass against a table that does not exist.
- **`scripts/ops/run025/verify_model_schema_parity.py`** does read a real
  database, but subtracts `alembic_check_excluded_tables()` from the comparison
  first — and that deferral register is precisely the set whose migrations never
  landed. Its `missing_tables` key can only ever report a table nobody has
  already agreed to defer, which is why it reports none of these sixteen.

`scripts/ops/run026/inventory_declared_vs_actual_tables.py` excludes nothing.

### Row counts are a separate question, and are not answered here

A table that exists and holds no rows is a different state, and usually a
legitimate one: a new tenant has no records yet. Seventeen tables on the deferral
register were reported in that state in production by the Run 021 measurement,
which recorded the `count(*)` queries it ran but not their per-table results — so
treat the seventeen as that work's finding rather than as re-derived here. It is
the safe direction to be uncertain in: **nothing in this work changes their
behaviour**, and no endpoint above them has been made to error. See §4.

Row counts can only be read from a deployment real users write to. The tooling
supports it (`--count-rows`) but demands `--environment-label`, because an empty
table on a freshly migrated local database says nothing whatsoever about
production.

---

## 2. The sixteen absent tables

All sixteen are already on the deferral register with named owners, and fourteen
of them are marked "migration coverage pending" — for those the honest
description is not "temporarily broken" but **never built**: the code exists, the
migration does not. The two exceptions are noted in the table and neither has a
reader.

The first seven are the production-verified set. The remaining nine rest on the
local reproduction only (§1), and none of them is read by anything.

| Table | Reader | Disclosed by |
|---|---|---|
| `document_approval_workflows` | `document_control` routes | §3 |
| `document_approval_instances` | `document_control` routes | §3 |
| `document_approval_actions` | `document_control` routes | §3 |
| `document_distributions` | `document_control` routes | §3 |
| `document_access_logs` | `document_control` routes | §3 |
| `obsolete_document_records` | `document_control` routes | §3 |
| `document_training_links` | **nothing** — declared, never queried | not disclosed (§4) |
| `ims_controls` | **nothing** | not disclosed (§4) |
| `ims_control_requirement_mappings` | **nothing** | not disclosed (§4) |
| `ims_objectives` | **nothing** | not disclosed (§4) |
| `ims_process_maps` | **nothing** | not disclosed (§4) |
| `management_reviews` | **nothing** | not disclosed (§4) |
| `management_review_inputs` | **nothing** | not disclosed (§4) |
| `unified_audit_plans` | **nothing** | not disclosed (§4) |
| `root_cause_analyses` | **nothing** — model retained after a migration dropped the table | not disclosed (§4) |
| `escalation_rules` | **nothing** — the ORM model is never queried | not disclosed (§4) |

The last two are the register's exceptions to "migration coverage pending":
`root_cause_analyses` was built and then dropped by a migration, and
`escalation_rules` is an ORM name for the migrated `escalation_rules_config`. So
"never built" is the wrong phrase for both — and immaterial, because neither is
read.

Only six of the sixteen have a reader. Every one of those six is read by
`src/api/routes/document_control.py`, and every one of the six is
production-verified absent.

---

## 3. What each affected surface now says

Router prefix `/api/v1/document-control`. The page is **Document Control**, a
top-level menu item (`/document-control` in `Layout.tsx`).

Every "Was: 500" below was **observed** against a database with these seven
tables dropped — `tests/integration/test_document_control_absent_table_disclosure.py`
run against the base commit fails 20 of 27 that way. It is **inferred** for
production, from the table being absent there and the handler querying it
unconditionally. No captured production response is quoted here: the Run 021
probes of these endpoints were unauthenticated and returned 401, and nobody is
going to reproduce a 500 in production to prove a point.

### Reads — 503 `MEASUREMENT_UNAVAILABLE`, naming the table

| Endpoint | Called by | Was | Now |
|---|---|---|---|
| `GET /workflows` | API only | 500 | 503, `missing_tables: [document_approval_workflows]` |
| `GET /{id}/access-log` | API only | 500 | 503, `missing_tables: [document_access_logs]` |

An empty array is not used, following PR #1404: for a list endpoint absence is
inherently coercible to empty — every defensive client writes `items ?? []` — so
the only signal a consumer cannot flatten back into "there are none" is
not-a-success.

### Writes — 503 `FEATURE_NOT_PROVISIONED`, stating that nothing was saved

| Endpoint | Called by | Now also guarantees |
|---|---|---|
| `POST /workflows` | API only | — |
| `POST /{id}/submit-for-approval` | **Document Control page** ("Submit for approval") | the document is **not** left in `pending_approval` |
| `POST /approvals/{id}/action` | API only | — |
| `POST /{id}/distribute` | **Document Control page** ("Distribute") | — |
| `POST /{id}/distributions/{id}/acknowledge` | **Document Control page** ("Acknowledge") | — |
| `POST /{id}/obsolete` | API only | the document is **not** marked obsolete without its retention record |

The last two guarantees are the reason the check happens before the write rather
than after it fails: each of these endpoints stages a change to
`controlled_documents` in the same transaction as its absent-table `INSERT`.

### Partially readable — served, with the unavailable part named

| Endpoint | Called by | Was | Now |
|---|---|---|---|
| `GET /{document_id}` | **Document Control page** (the detail pane) | 500 — no controlled document's detail could be viewed at all | 200 with the document, its versions and its metadata, plus an `unavailable` block naming `document_distributions` and `document_access_logs` |
| `GET /summary` | API only | 500 — all seven measurable figures lost | 200 with the seven figures; `pending_acknowledgments` omitted and named under `unmeasurable` |

`GET /{document_id}` still sends `distributions: []`, because the one consumer
reads `detail.distributions.length` and a missing key would crash the page. That
empty array is byte-identical to "no controlled copies were issued", so the
`unavailable` block beside it is load-bearing rather than decorative, and
`frontend/src/pages/DocumentControl.tsx` consults it before drawing anything over
that list.

`GET /summary` omits `pending_acknowledgments` rather than sending `0`, which is
the defect PR #1402 fixed on the acknowledgment dashboard, and rather than
sending `null`, from which a client writing `?? 0` would rebuild the same lie.

The view is still counted when it cannot be logged, and the skipped log write is
disclosed. No trail is recorded either way while the table is absent, so failing
the read would buy no audit integrity and would hide the gap behind a generic
500 — an auditor needs to see it in the payload, not only in Sentry.

### Why 503 and not 501

`FEATURE_NOT_PROVISIONED` is 503. RFC 9110 scopes 501 to a method the server does
not support at all, which is untrue here — the handler works the moment the
migration lands — and RFC 9111 makes 501 heuristically cacheable, so a cached 501
could outlive the fix. 503 is not heuristically cacheable.

`Retry-After` is deliberately never set. For an absent table "try later" is only
true after a deploy, so naming a number of seconds would be a guess dressed as a
fact. `details.provisioning_state` carries the distinction instead, and the
frontend exempts both codes from the "Server error:" prefix and from any copy
inviting a retry.

---

## 4. What was deliberately left alone

Three separate categories, all judged to need no change.

### Ten absent tables with no reader

`document_training_links`, the seven IMS / management-review tables,
`root_cause_analyses` and `escalation_rules` are declared by models that no route
or service ever queries. There is no surface to disclose anything on, and adding
one would be inventing a feature to apologise for. Verified by searching for both
the model class names and the table names across `src/`; the only remaining
references are foreign keys between the absent tables themselves.

Two near-misses worth naming, because both look like readers and are not:

- `EscalationRule` in `src/domain/services/workflow_service.py` is an unrelated
  `str` Enum, and `escalation_rules` in `workflow_engine.py` and
  `schemas/workflows.py` is a JSON **column** on `workflow_definitions`.
- `root_cause_analyses` is a model retained in metadata after a migration dropped
  the physical table. The RTA surfaces users actually reach do not use it.

### The ISO 27001 surfaces, which work

`src/api/routes/iso27001.py` reads `src/domain/models/iso27001.py`, whose tables —
`information_assets`, `iso27001_controls`, `soa_control_entries`,
`security_incidents`, `access_control_records`, `business_continuity_plans`,
`supplier_security_assessments` — **are all present**, in the local Alembic build
and, per Run 021, in production. They hold no rows, so those endpoints return
empty lists, and that is a true answer. The similarly named
`ims_*` tables in `src/domain/models/ims_unification.py` are a different, unread
set. Anyone reading "ISO 27001 controls are absent" from the deferral register is
reading the wrong row.

### The seventeen present-and-empty tables

Zero rows is what a customer with no records looks like. Turning that into an
error would be the mirror image of the defect being fixed here, and worse, because
it would break software that works. No endpoint above them was changed.

That holds regardless of how firmly the seventeen is established (§1): an
uncertain row count is not a reason to change behaviour, only a reason not to.
The suite pins this directly — `TestAReadThatHappened` asserts that a present,
empty distribution list, workflow list and access log each still answer `200`
with `[]` and no disclosure attached, and those assertions pass on the base
commit as well as after the change.

Whether those capabilities — ISO 27001 controls, the Statement of Applicability,
management review, supplier security assessment — are in scope at all is a
product question, not an engineering one, and it is not answered by this document.

---

## Related

- Deferral register: [`docs/governance/alembic_check_excluded_tables.md`](../governance/alembic_check_excluded_tables.md)
- Inventory tool: `scripts/ops/run026/inventory_declared_vs_actual_tables.py`
- Precedent: PR #1402 (a dashboard reporting 0% when compliance was unmeasurable), PR #1404 (`/my-pending` answering an unreadable table with an empty reading queue)
- Tests: `tests/integration/test_document_control_absent_table_disclosure.py`, `frontend/src/pages/__tests__/DocumentControlUnavailable.test.tsx`
