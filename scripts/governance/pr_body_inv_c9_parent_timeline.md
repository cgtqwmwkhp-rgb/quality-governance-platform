# Change Ledger (CL-INV-C9-PARENT-TIMELINE)

> Adjacent, not fixed here: the origin toggle narrows the page the endpoint returned, because the
> panel is presentational and the API filter (`?event_type=`) is owned by `InvestigationDetail.tsx`
> (C7). `?event_type=SOURCE_AUDIT` / `SOURCE_RUNNING_SHEET` already work server-side for whoever
> wires them. No findings table (C7), no pack content (C13), no C15 graphics.

## 1) Summary
- **Feature / Change name:** INV-C9 — timeline includes the parent source chronology
- **User goal:** D7. The timeline stopped at the investigation boundary. `GET
  /investigations/{id}/timeline` queried `investigation_revision_events` and nothing else, and the
  frontend spine merged five feeds that were all investigation-scoped. Everything the source case
  recorded before the investigation was raised — and everything still being written to it —
  was invisible from the investigation, so the investigator had to open the incident in another
  tab to reconstruct the order events happened in. Absorbs PR-13 (feed merge) and PR-14
  (chronology rendering with a source-vs-investigation filter).
- **In scope:** New read-only module that loads the parent record's `audit_log_entries` and its
  register's running sheet; the timeline GET merges those with the investigation's own revision
  events; `event_metadata.origin` distinguishes them; the spine and the timeline panel label and
  filter by origin.
- **Out of scope:** findings table (C7), pack rendering (C13), C15 graphics, `InvestigationDetail.tsx`
  (C7 owns it — the panel it already mounts needed no prop change), OpenAPI contract files (C7),
  `investigation_data_writer`/reader, alembic.
- **Feature flag / kill switch:** None. Kill SHA = LIVE `755dc8153022`. Read-only change; reverting
  the squash restores the investigation-only timeline with no data step.

## 2) Impact Map (what changed)
- **Backend:** `src/domain/services/investigation_parent_timeline.py` (new — parent-feed queries,
  synthetic ids, origin metadata, UTC normalisation); `src/api/routes/investigations.py` — the
  timeline GET merges the two parent feeds and stamps origin on its own rows, and the manual-entry
  POST stamps `origin: "investigation"` at write time.
- **Frontend:** `frontend/src/pages/investigation/activitySpine.ts` — `origin` on every spine item,
  a `source` kind, `filterActivitySpineByOrigin`; `InvestigationTimeline.tsx` — origin toggle
  (All origins / Investigation / Source record) and the source-record badge.
- **i18n:** four `investigations.timeline.origin_*` keys in `en.json` and `cy.json`.
- **APIs:** No contract change. Same route, same `InvestigationTimelineEventResponse` fields; origin
  travels inside the existing `event_metadata` dict rather than as a new top-level field, so
  `openapi-baseline.json` and `docs/contracts/openapi.json` are untouched.
- **Database / flags:** none. No column, no migration — three existing tables are read.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive. Investigation revision events keep their ids, ordering and
  fields. Parent rows arrive as extra items in the same shape. A client that ignores
  `event_metadata` sees a longer timeline, not a different one.
- **Ids:** revision-event ids are unchanged. Parent rows take `-(source_row_id * 10 + feed_code)`
  with a distinct single-digit code per feed: negative, so disjoint from the positive autoincrement
  ids; injective in `(row_id, feed)`, so the two parent feeds cannot collide; reversible, and the
  originating row id is also carried as `event_metadata.source_row_id`. Covered by a test that puts
  a revision event, an audit row and a running-sheet row all on row number 5.
- **Ordering and pagination:** still created_at DESC, id DESC, but the feeds must be ordered
  *together* before the page is cut, which rules out an SQL OFFSET on either. The merge window is
  bounded — newest 1000 revision events, newest 200 rows per parent feed — and `total` counts that
  window, so it stays consistent with what paging can actually reach instead of promising rows no
  page would return. Ties break on id DESC, which puts the investigation's own event first:
  arbitrary, but deterministic, which is what pagination needs.
- **Timestamps:** `audit_log_entries.timestamp` is `NaiveUTCDateTime`; the `created_at` columns are
  `DateTime(timezone=True)`. Sorting them together without normalising raises `TypeError: can't
  compare offset-naive and offset-aware datetimes`. Every row is normalised to aware UTC (both
  columns are documented UTC), which also stops a naive value being parsed as local time in the
  browser.
- **Breaking changes:** none. `total` now counts the merged window rather than revision events
  alone; that is the point of the change, not a contract break.
- **Migration plan / Rollback strategy (DB):** none needed either way — nothing is written.
- **Read-path safety:** every parent query filters on `tenant_id` and on the parent record's id, and
  is `LIMIT`-ed. A missing tenant fails closed (no query at all, investigation events only) rather
  than reading unscoped. The four running-sheet tables have a nullable `tenant_id`, so equality
  filtering excludes any legacy row that never recorded a tenant — the fail-closed direction, and
  the deliberate one. An unsupported or absent source type, an unparseable entity id, an
  `?event_type=` no parent row can satisfy, malformed JSON columns and an undated row are all
  handled without a 500 and without a query being issued pointlessly.

## Compliance Delta
- **PII touched?** Yes. Two things now reach an audience they did not: the parent record's audit
  descriptions and actor names, and the running-sheet narrative (`__data_classification__` =
  `C4_RESTRICTED`). Both are read by the investigation's existing authorisation
  (`_get_investigation_or_404`: tenant refused first, then run access) and only for the record the
  investigation is already declared to be about. No new collection, no new processor, no new
  retention.
- **Deliberate redaction:** `audit_log_entries.old_values` / `new_values` are **not** copied. For an
  incident those hold the whole mutation payload — reporter, injured person, free-text description.
  The row carries the audit entry's description and the *names* of the changed fields
  (`event_metadata.source_changed_fields`); the values stay in the Admin Audit Trail behind its own
  authorisation. A test asserts payload values do not appear anywhere in the serialised row.
- **Actor names:** resolved through the existing `_actor_names_for_events` join, so one `users`
  lookup covers the page and a renamed user reads correctly. Fallback order for a parent row is the
  live user, then the audit entry's own denormalised `user_name` / `user_email` (already returned by
  the Admin Audit Trail API today), then nothing. A running-sheet `author_email` is used only when
  the entry names no user at all. No name is derived, inferred or invented.
- **Lawful basis / retention:** unchanged (legal obligation / legitimate interest; existing
  incident and investigation retention). Nothing new is logged: the two log lines added are a
  fail-closed warning and a dropped-row count, neither carrying content or identity.
- **QGP never writes PAMS.** Nothing here writes anything. No bulk Users, no Entra.
- **What this PR does not claim:** that the origin filter is server-side (it narrows the fetched
  page), that the whole history of a decade-old incident is on one timeline (the window is capped),
  or that the parent record is linkable from a source row (no tab on this page owns it).

## 4) Acceptance Criteria (AC)
- [x] AC-01: The timeline returns `InvestigationTimelineEventResponse` items unchanged — no new
  top-level field, so no OpenAPI conflict with C7.
- [x] AC-02: Investigation revision events, the parent record's `audit_log_entries` and the
  matching running sheet are merged into one created_at-DESC chronology, across naive and
  tz-aware timestamps.
- [x] AC-03: Every row declares an origin — `source` for parent rows, `investigation` for the
  investigation's own; a pre-C9 event with no metadata reads as `investigation`, and the ORM row is
  not mutated to say so.
- [x] AC-04: Existing `event_metadata` survives the origin stamp.
- [x] AC-05: Parent-row ids cannot collide with a revision-event id or with each other, and encode
  their feed and source row reversibly.
- [x] AC-06: Every parent query is tenant-filtered, keyed on the parent record's id and capped at
  200 rows; an investigation with `tenant_id = None` issues no parent query at all.
- [x] AC-07: The parent record's field *values* stay out of the timeline; only changed-field names
  cross over.
- [x] AC-08: `reporting_incident → incident`, `near_miss → near_miss`,
  `road_traffic_collision → rta`, `complaint → complaint` — the values those services actually
  write. Child types (`incident_action`, `rta_action`) are excluded: their `entity_id` is an action
  id, not the case's.
- [x] AC-09: No source, an unsupported source type, an unparseable source id or an empty parent
  returns the investigation's own events without a 500.
- [x] AC-10: Pages are cut after the merge, not per feed; `total` and `pages` describe the merged
  window and a page past the end is empty rather than an error.
- [x] AC-11: `?event_type=SOURCE_RUNNING_SHEET` reads only that feed;
  `?event_type=STATUS_CHANGED` skips the parent queries entirely rather than running and
  discarding them.
- [x] AC-12: Parent-row actor names prefer the live `users` join, fall back to the recorded name,
  and use a running-sheet email only when the entry has no `author_id`.
- [x] AC-13: The spine and the panel distinguish source from investigation — a `source` kind, a
  "Source record" badge, and an origin toggle that is separate from the event_type filter because
  that value is forwarded to the API.
- [x] AC-14: Every origin label resolves from `en.json` rather than a developer fallback, and Welsh
  parity is kept (`cy.json`).

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_parent_timeline.py` (30 tests, all passing): merge
  order across naive/aware timestamps, origin on all three feeds, no ORM mutation, id collision,
  synthetic-id reversibility, tenant fail-closed, tenant/limit SQL assertions on compiled
  statements, the four register mappings, child-type exclusion, absent/unsupported source,
  event_type shortcuts, merge-then-slice pagination over four pages, deterministic tie-break,
  payload redaction, actor-name precedence, undated row, malformed JSON columns.
- [x] Regression — `pytest tests/unit -k investigation` (274 passed, none skipped), including
  `test_investigation_timeline_actor_names.py` unchanged.
- [x] Frontend — `vitest run` on `activitySpine.test.ts`, `InvestigationTimeline.test.tsx`,
  `InvestigationTimelineI18n.test.tsx` (25 passed): origin parsing and default, interleaving by
  date, `src-`/`rev-` key separation, source-row titling, origin filter composition with the
  event_type filter, rendered "Source record" badge, click-through of the three origin buttons,
  `aria-pressed`, and every origin key resolving from the real `en.json`.
- [x] Lint/type — `black`, `isort`, `flake8` clean on the changed Python; `tsc --noEmit` and
  `eslint --max-warnings 0` clean on the changed frontend; `node scripts/i18n-check.mjs` passes
  (4552 keys, Welsh coverage 90.9%); `scripts/check_import_boundaries.py` OK.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open the timeline on an investigation raised from an incident — the incident's own
  audit rows and running-sheet notes appear interleaved by date with the investigation's events,
  each badged "Source record".
- [x] CUJ-02: Filter to "Investigation" — only the investigation's own rows remain; filter to
  "Source record" — only the parent's; back to "All origins" — both.
- [x] CUJ-03: Page through a timeline whose two feeds interleave — page boundaries follow the
  merged order, no row is repeated or skipped, and the page past the end is empty.
- [x] CUJ-04: Open an investigation whose source record has no audit or running-sheet rows, or
  whose source type has no feed — the investigation's own timeline renders as before.
- [x] CUJ-05: An investigation with no tenant recorded shows its own events and reads nothing from
  any parent table.
- [x] CUJ-06: A source audit row for an incident field change shows which field changed and who
  changed it, and does not show the old or new value.

## 7) Observability & Ops
- **Logs:** two warnings only — `investigation_parent_timeline_fail_closed` (a run with no tenant
  asked for parent rows) and `investigation_parent_timeline_dropped_undated` (a count). Neither
  carries narrative content or identity, so no investigation PII reaches application logs.
- **Metrics:** none added.
- **Query cost:** two extra indexed SELECTs per timeline page —
  `ix_audit_log_entity (entity_type, entity_id)` plus the tenant filter, and the running sheet's
  `(tenant_id, parent_id)` index — both `LIMIT 200`.

## 8) Release Plan
- **Staging / prod:** no schema change and no flag. Confirm `/healthz` and
  `/api/v1/meta/version` `build_sha` on the merge SHA, then open the timeline on a staging
  investigation created from an incident that has running-sheet entries and confirm the source
  rows appear, are badged, and filter.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a source row attributed to the wrong record or tenant, a parent field value
  appearing in the timeline, a duplicate id in a page, or the timeline 500-ing on an investigation
  whose source is missing.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `755dc8153022`.
  No data step — the change is read-only, and the only thing written differently is a
  `origin: "investigation"` key added to new manual-entry metadata, which pre-C9 readers ignore.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (no contract change; origin inside `event_metadata`)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
