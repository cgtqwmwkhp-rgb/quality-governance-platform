# Change Ledger (CL-INV-C15-PACK-CHRONOLOGY)

> **Read this first — what this PR does not do.** The chronology figure draws whenever the pack
> renderer is handed a timeline feed, and nothing in production hands it one yet. The endpoint that
> builds the pack PDF payload (`src/api/routes/investigations.py`) and the pack generator
> (`investigation_service.generate_customer_pack`) are both outside this PR's file boundary — C9
> owns the first, C13 the second — so an existing pack renders exactly as it did before this
> change. What ships here is the renderer, the drawing layer, the regression harness and a stated
> contract for the one line a later PR adds. Wiring the feed is a one-key change to the payload
> dict; inventing it here would have meant querying the parent audit log and running sheets from
> inside a PDF generator, which is the wrong place for a tenant-scoped read and is rejected below.

## 1) Summary
- **Feature / Change name:** INV-C15 — pack chronology figure and drawing harness
- **User goal:** The customer pack is a wall of headings and values. A reader cannot see the shape
  of the case: that the incident ran for a fortnight before anyone raised an investigation, that
  the source record kept being written to afterwards, or where the investigation's own decisions
  sit against that. INV-C9 made that distinction available in the timeline
  (`event_metadata.origin`); C15 draws it. Absorbs PR-27 (vector drawing helpers) and PR-28
  (graphical chronology + golden-fixture PDF regression).
- **In scope:** a new drawing module (text safety, colour arithmetic, page-space reservation,
  lines, rectangles, markers, arrows, legends, time-axis scaling); a two-lane chronology figure
  built from those primitives; a `Chronology` section in the pack PDF that renders the figure, the
  most recent entries, and where the events came from; a golden-fixture harness that records
  drawing calls so a figure regression is a readable diff.
- **Out of scope:** supplying the feed (route — C9/C7 own that file); pack content generation and
  rendering findings/RCA/contributing factors into the pack (C13); the ICAM diagram (C16 — it
  imports Part 1 of the new module); `InvestigationDetail.tsx`, `InvestigationTimeline.tsx`,
  `activitySpine.ts`, OpenAPI contract files, findings modules, alembic, competence, PAMS, Entra.
- **Feature flag / kill switch:** None needed. Kill SHA = LIVE `1de9c8e13883` (INV-C9). The
  section is inert until a caller supplies a feed, which is itself the kill switch: stop passing
  the events and the pack is unchanged.

## 2) Impact Map (what changed)
- **Backend:** `src/domain/services/investigation_pack_draw.py` (new — Part 1 vector/text/layout
  primitives, Part 2 chronology normalisation and figure); `src/domain/services/
  investigation_pack_pdf.py` — `build_pdf_bytes` takes an optional `timeline_events`, a new
  `chronology_feed()` resolves where events come from, and `_render_chronology` draws the section.
- **Moved, not rewritten:** `_pdf_safe`, `_fit_cell_text` and `humanise_key` now live in the
  drawing module and are aliased at their old names in the renderer, so the drawing layer and the
  pack cannot drift into two versions of "what is safe to put on a Helvetica page". Behaviour is
  identical and the existing tests that call `pack_pdf._fit_cell_text` / `humanise_key` are
  untouched and still pass.
- **Frontend:** none.
- **APIs:** No contract change. No route touched, no schema touched, no OpenAPI change — the new
  argument is a keyword with a default on an internal service method.
- **Database / flags:** none. No column, no migration, no flag, no query.
- **Workflows/jobs:** none.
- **Tests:** `tests/unit/_pdf_golden.py` (new harness), `tests/unit/
  test_investigation_pack_draw.py` (new, 63 tests), 19 new tests in
  `tests/unit/test_investigation_pack_pdf.py`, two golden fixtures plus a README under
  `tests/fixtures/golden/pdf/`.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive and inert by default. `timeline_events` defaults to `None`;
  with no feed the `Chronology` section is omitted entirely and the rendered pack is the C14 pack.
- **Three ways in, one shape:** the argument, `pack["timeline_events"]`, or
  `content["chronology"]` (a list, or a mapping with an `events` list). All three take the shape
  `GET /investigations/{id}/timeline` already serialises, so a later PR wires one key rather than
  inventing a second event format. Origin is read from `event_metadata["origin"]` — never
  re-derived from ids, event types or table names.
- **Absent is not empty.** No feed at all omits the section, because printing "no events" would
  claim the timeline had been consulted when nothing asked it. An empty feed prints "No chronology
  entries are recorded for this investigation." Those two cases are separately tested.
- **Read-path safety:** the renderer performs no reads. It has no session, no tenant id and no way
  to widen what the caller was allowed to see — which is why the events are an argument rather
  than a query. The feed must already be the authorised, tenant-scoped timeline
  (`load_parent_timeline_rows` is tenant-filtered and fails closed); that contract is stated in
  `chronology_feed`'s docstring, and this PR adds no code path that could bypass it.
- **Bounded output:** newest 500 events are placed (`CHRONOLOGY_EVENT_CAP`), 12 are listed in
  words, each detail is capped at 240 latin-1-safe characters. 900 events in, 500 markers drawn, a
  24 KB PDF in 0.24 s, and the pack states how many earlier entries are not shown.
- **Page geometry:** absolute vector drawing does not trigger fpdf2's auto page break, so a figure
  at the foot of a page would paint over the footer. `reserve_frame` breaks the page *before* any
  ink is laid down, and clamps a figure taller than a page instead of overrunning. Verified
  visually on a pack whose chronology lands 12 mm above the break margin.
- **Origin constants:** copied into the drawing module rather than imported from the C9 module,
  which pulls in four ORM models — the drawing layer must not import the database. A test pins the
  two spellings equal, so a rename on the C9 side fails loudly instead of silently emptying a lane.
- **Breaking changes:** none.
- **Migration plan / Rollback strategy (DB):** none needed either way — nothing is written.

## Compliance Delta
- **PII touched?** Yes, potentially — and that is why the figure is **internal-audience only**. A
  timeline entry carries an actor name and the source record's running-sheet narrative
  (`C4_RESTRICTED`). The pack's redaction pass walks `content["sections"]` and rewrites recorded
  identity fields; it never sees a chronology, so drawing one into an external pack would release
  identities the pack claims to have redacted. `internal_customer` renders the figure; external,
  unknown and absent audiences get a stated withholding instead — the same fail-closed direction
  `confidentiality_notice` already takes for an unrecognised audience. A test asserts the actor
  name and the running-sheet narrative are absent from the rendered external PDF.
- **Widening the audience is a product decision**, not a rendering one: it needs a redaction rule
  for timeline data. This PR does not invent one.
- **Provenance is stated on the page.** A pack-sourced chronology says it is covered by the
  content checksum; a render-time chronology says it is not part of the stored payload and not
  covered by the checksum. Without that line, a reader could checksum the payload, fail to find
  the chronology in it and be right to distrust the document. The `Pack integrity` paragraph
  itself is C1/C14 wording and is left alone.
- **Lawful basis / retention:** unchanged. No new collection, no new processor, no new retention,
  no new field stored anywhere.
- **Logs:** two lines, neither carrying investigation content or identity — a figure-render failure
  (`logger.exception` with the pack UUID) and a frame-clamp warning carrying two numbers.
- **QGP never writes PAMS.** Nothing here writes anything at all. No bulk Users, no Entra.
- **What this PR does not claim:** that a production pack shows a chronology today (no caller
  supplies the feed yet); that the entry list is the whole timeline (12 of N, stated); that
  timeline data is redacted (it is not, which is why external packs withhold it); or that the
  golden fixtures pin rendered pixels (they pin the drawing calls — see below).

## 4) Acceptance Criteria (AC)
- [x] AC-01: A chronology feed renders a vector figure in the pack: a time axis, source-record
  entries above it and the investigation's own below, positioned by time rather than by index.
- [x] AC-02: The origin split is read from `event_metadata["origin"]` exactly as INV-C9 writes it;
  a pre-C9 event with no metadata reads as the investigation's own, and the two origin constants
  are pinned equal to the C9 module by a test.
- [x] AC-03: No feed omits the section; an empty feed states the absence; neither 500s and neither
  invents an event.
- [x] AC-04: Only `internal_customer` gets the chronology. External and unrecognised audiences get
  a stated withholding, and no actor name or running-sheet narrative reaches the PDF.
- [x] AC-05: The pack states where the events came from and whether the content checksum covers
  them.
- [x] AC-06: Undated, malformed and non-list input degrade honestly — counted and declared, never
  silently dropped, never raised.
- [x] AC-07: Output is bounded: newest 500 placed, 12 listed, 240 characters per detail, and the
  pack says how many earlier entries are not shown.
- [x] AC-08: The figure never paints over the footer — the page breaks before drawing starts, and
  a figure taller than a page is clamped.
- [x] AC-09: A figure that fails to draw degrades to the entry list with the failure stated, and
  leaves font, line width, dash and colour state clean for the next section.
- [x] AC-10: Drawing primitives are reusable by C13/C16 without importing pack semantics or the
  database: text safety, colour arithmetic, frames, page-space reservation, lines, rectangles, four
  marker shapes, arrows, legends and time-axis scaling.
- [x] AC-11: Marker shape carries meaning as well as colour (circle vs square), so the figure still
  separates its two series in mono print.
- [x] AC-12: A golden-fixture harness records drawing calls against a real `FPDF`, fails on a
  changed drawing, fails on a missing fixture, and is reusable by the C16 ICAM diagram.
- [x] AC-13: All figure and entry text is latin-1 safe, and dates are locale-independent so a
  fixture cannot flap with the host locale.
- [x] AC-14: Existing pack rendering is unchanged — sections, withheld sections, evidence schedule,
  redaction summary, branding, footer and pack integrity all still render, with the moved text
  helpers behaving identically.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_pack_draw.py`: **63 passed**. Text safety and
  ellipsizing, colour maths and WCAG contrast, frame geometry, page-break reservation, over-tall
  clamp, state restoration including on exception, marker shapes and centring, arrow head, legend
  truncation, time scaling with a zero span, the C9 origin-constant pin, normalisation (ordering
  across string/datetime/naive/offset timestamps, origin default, label fallback, shouting event
  types, undated and junk entries, row objects, bounded latin-1 detail, non-scalar values, the
  cap), summary wording, both golden fixtures, lane separation, time-not-index placement,
  colliding timestamps, frame containment, page break, clean state, latin-1 output, and three
  harness self-tests.
- [x] Unit — `tests/unit/test_investigation_pack_pdf.py`: **49 passed** (30 pre-existing unchanged,
  19 new). Section omitted with no feed, figure + entries rendered for an internal pack, document
  grows by more than the words added, stored vs render-time provenance wording, bare-list and
  mapping stored feeds, feed precedence, absent vs empty, non-list feed ignored, external
  withholding with no actor name or narrative on the page, unknown/blank/None audience fails
  closed, external empty feed does not claim a withholding, undated entries declared, 700 events
  bounded to "12 of 500" with "200 earlier entries are not shown", a failing figure degrading to
  the entry list, surrounding sections intact, and non-latin-1 chronology text.
- [x] Regression — `pytest tests/unit -k "investigation or pack"`: **436 passed, none skipped**.
  No existing test was skipped, loosened or rewritten.
- [x] Edge probes (run by hand, not committed): 900 events → 500 markers, 24 KB, 0.24 s; a
  5000-character unbreakable token in an entry detail; year 1 to year 9999 timestamps; a payload
  with `content: None` carrying only a chronology. All render a valid PDF.
- [x] Visual — pack rendered to PNG and read: two-lane figure with legend, axis ticks, dated ends;
  and a second pack whose figure lands at the foot of page 1 without touching the footer.
- [x] Lint/type — `black --check`, `isort --check-only`, `flake8` clean on all five files; `mypy`
  clean on both source modules; `scripts/check_import_boundaries.py` OK (the new module imports
  nothing but the standard library).
- [ ] Full CI — linked after PR checks.

### Why the golden fixtures are drawing calls, not PDF bytes
A committed `.pdf` carries a creation timestamp and the fpdf2 version in `/Producer`, and its page
content is zlib-compressed, so it would differ on every run and a real regression would surface as
a binary diff. `requirements.txt` pins `fpdf2>=2.8.0,<3.0.0`, so a patch release emitting the same
drawing with different operator formatting would fail a byte golden while nothing about the figure
had changed. Instead a proxy wraps a **real** `FPDF` and records the calls the drawing layer makes
through it — geometry, colours, shapes, fonts, exact strings — then delegates each one, so text
measurement, page breaks and rendering stay real and the produced document is still asserted to be
a valid PDF. A missing fixture fails rather than being written: a golden test that writes its own
expectation on first run passes in CI while asserting nothing.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Render an internal pack with a chronology feed — the figure shows the source case's
  entries above the axis and the investigation's below, spaced by real elapsed time, with a legend,
  dated axis ends, a factual summary line and the twelve most recent entries in words.
- [x] CUJ-02: Render an external pack with the same feed — no figure, no actor name, no
  running-sheet narrative, and a sentence saying the chronology is withheld and why.
- [x] CUJ-03: Render a pack with no feed (today's production path) — no `Chronology` section at
  all. Verified by rendering the same payload through the module as it exists on `1de9c8e13883`
  and through this branch: **identical bytes** once the PDF creation date is stripped, for both
  audiences.
- [x] CUJ-04: Render a pack whose feed is empty — the pack states there are no entries rather than
  drawing an empty axis or claiming a span.
- [x] CUJ-05: Render a pack whose sections fill page 1 — the figure moves to the next page instead
  of painting over the footer, and the entry list follows it.
- [x] CUJ-06: Render a pack with 700 events, some undated and some malformed — bounded output, and
  the counts dropped and unplaceable both stated on the page.
- [x] CUJ-07: Change the figure's geometry and re-run — the golden fixture fails with the first
  differing operation named, and `UPDATE_PDF_GOLDEN=1` regenerates it while still failing so the
  diff must be reviewed.

## 7) Observability & Ops
- **Logs:** `Investigation pack chronology figure failed for pack <uuid>` (exception, no event
  content) and `pack_draw_frame_clamped requested=… page=…` (two numbers). No investigation PII
  reaches application logs.
- **Metrics:** none added.
- **Query cost:** zero. No query is issued by this PR — the renderer draws what it is handed.
- **Render cost:** measured above; the figure is bounded by the 500-event cap.

## 8) Release Plan
- **Staging / prod:** no schema change, no flag, no contract change. Confirm `/healthz` and
  `/api/v1/meta/version` `build_sha` on the merge SHA, then download an existing customer pack PDF
  from staging and confirm it is unchanged (no `Chronology` section), which is the correct
  behaviour until a later PR supplies the feed.
- **Note for the next PR:** to switch the figure on, add `"timeline_events": items` to the payload
  dict in `download_customer_pack_pdf`, or store `content["chronology"] = {"events": items}` at
  pack generation — the second is preferable because the checksum then covers the chronology and
  the pack says so.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a chronology reaching an external pack, an event drawn at a time it did not
  happen, a figure painting over the footer or another section, or a pack export failing where it
  previously succeeded.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `1de9c8e13883`.
  No data step — nothing is written, nothing is migrated, and no stored pack changes.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration
- Golden fixtures and their rationale: `tests/fixtures/golden/pdf/README.md`

## Rejected alternatives
- **Query the timeline from the PDF generator.** It would have made the figure visible in
  production inside this PR's file boundary. Rejected: the pack renderer is deliberately a leaf
  that sees only the stored, already-redacted payload — that property is why it cannot leak what a
  pack withheld. Giving it a session and a tenant-scoped read of the parent audit log and running
  sheets would trade a permanent architectural guarantee for one PR's visible output, and the read
  it needs already exists in C9 behind the endpoint's authorisation.
- **A de-identified figure for external packs** (dates and markers only, no names or narrative).
  Rejected for now: it requires deciding what "de-identified enough" means for timeline data, and
  narrative text is already documented as not redacted. That is a product decision with a lock,
  not a rendering choice, and "internal at least" is what was asked for.
- **Byte-comparison golden PDFs.** Rejected for the reasons set out above.

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (no contract change; new keyword argument with a default)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag; the section is inert until a caller supplies a feed)
- [x] **Gate 5:** Production verification plan + monitoring ready
