# Run 021 — Code Verification Review (Phases A–C)

**Reviewed:** 26 July 2026 · **Subject:** `QGP-Run021-Cursor-Pack` (208 defects, verdict NO-GO)
**Method:** register reconciliation across all five documents, then claim-by-claim verification of every P0
and every architectural finding against the source at `quality-governance-platform`.
**Status:** review complete. No code changed. Nothing in the pack has been actioned yet.

---

## 0. Verdict on the pack

**Accept it. Then fix three mechanisms before anyone writes code.**

The register is the strongest UAT artefact this programme has produced. Every quantitative claim I could
check held up: the CSV, the XLSX and the register markdown agree **exactly** — 208 rows, identical
severities, no duplicate IDs, no row present in one and absent from another, and all 208 are written up
longhand in the full report. Repro rates are stated per defect, coverage gaps are declared rather than
buried, and thirteen findings were withdrawn or rewritten when they failed scrutiny. That last discipline
is what makes the rest credible, and it is rare.

Three things need correcting before implementation, and they are not cosmetic:

1. **The work order's headline number is wrong** — it says 172 defects; the true figure is 208. It is the
   document the README instructs an engineer to scope from.
2. **Three findings are real but diagnosed wrongly**, and each wrong diagnosis points engineering at code
   that does not exist. One of them is the finding the pack calls "the single most important in this report".
3. **The delivery plan omits its own highest-value fix** from Wave 1.

Against that, the review produced two things the run could not have got from a browser: **the root cause of
PX-281**, which the pack correctly left open, and **the mechanism behind PX-178 and PX-191**, which turns out
to be a single deployment event that is documented in this repository's own CI workflow comments.

---

## 1. Register integrity

### 1.1 The data is clean

| Check | Result |
|---|---|
| CSV rows | 208 |
| CSV vs XLSX vs register markdown | identical — severities, titles, IDs all agree |
| Severity split | P0 ×11, P1 ×50, P2 ×92, P3 ×55 (sums to 208) |
| Duplicate IDs | none |
| Blank mandatory fields | none |
| Defects in the register but missing from the full report | none |
| Inline severity claims in prose vs the register | all consistent |

### 1.2 Corrections required in the prose

| # | Document | Says | Should say |
|---|---|---|---|
| 1 | Work order, line 5 | `172 defects` | **`208 defects`** — the only wrong headline number in the pack, in the document engineers scope from |
| 2 | Work order §4, GROUP 9 | lists PX-307 in "the P3 set" | PX-307 is **P2**. The register, the CSV, the XLSX and the portal report's own table all say P2 |
| 3 | Portal report §1 | `9 P2 · 14 P3` | **`10 P2 · 13 P3`**. Its own table in §3 disagrees with its summary — the same PX-307 error |
| 4 | Work order §0 (Phase B) | "nine findings that were withdrawn" | **thirteen**. README says "Twelve". The register's table has 13 data rows |
| 5 | README | "five-wave delivery sequence" | **six** waves are defined (Wave 0 through Wave 5) |
| 6 | Work order §4, GROUP 1 | values are in `claude/QGP-Lookup-Configuration-Values.md` | the pack ships it at **`04-reference/`** |
| 7 | Work order §3.1 heading | `(P0 — PX-255, PX-216, PX-234, PX-248)` | only PX-255 and PX-248 are P0; **PX-216 and PX-234 are P1** |
| 8 | Work order §7, E1.4 | "see GROUP 1 of §3.1" | §3.1 contains no GROUPs — cite §3.1 directly |
| 9 | Portal report | omits PX-324 through PX-331 entirely | it is **stale**. Eight portal defects are missing from it, including **PX-327, a P0** the work order calls the highest-value fix in the document. Its stated "2 P0" should be 3 |

### 1.3 One unexplained gap

Five IDs in the range PX-119…PX-331 are absent from the register: **PX-146, PX-185, PX-190, PX-241, PX-296**.
Four are accounted for in the withdrawn table. **PX-190 appears in no document in the pack.** Either a
finding was withdrawn without being recorded — which would breach the discipline the register otherwise
holds to — or one was lost. It sits between PX-189 and PX-191, both Run 021 P3s, so it was allocated during
the run. Worth resolving for the audit trail of the register itself.

### 1.4 One ID conflation to watch

The 422 on the complaint form is **PX-281**. The two-click stepper defect is **PX-282**. The portal report
§6 attributes the 422 to PX-282 ("Complaint blocked by PX-282 (HTTP 422)"). The README's fourth note says
"PX-282 still needs an independent root cause" where it means PX-281's root cause. Both are now resolved
below, so this matters mainly for not fixing the wrong thing.

---

## 2. The three findings that are real but diagnosed wrongly

These are the highest-value corrections in this review. In each case the **symptom is confirmed** and the
severity is justified, but the stated mechanism does not exist in the code — so the fix instruction in the
work order would send an engineer looking for something that is not there.

### 2.1 PX-178 — confirmed as a symptom, refuted as a mechanism, and worse than reported

**The work order says:** locate the API base-URL resolution and "any health-check-driven fallback"; confirm
whether this is intentional failover or misconfiguration.

**There is no failover in the frontend.** The API base URL is resolved **once**, at module load, from a
build-time constant, and is never re-resolved:

```
frontend/src/config/apiBase.ts:171   export const API_BASE_URL = getApiBaseUrl()
frontend/src/api/client.ts:77        baseURL: HTTPS_API_BASE
```

The axios interceptors only enforce HTTPS and refresh auth; they never swap host. The service worker
(`frontend/public/sw.js:134-190`) rewrites `http`→`https` on the *same* URL and uses network-only for API
calls. The `/readyz` probes the tester saw immediately before the switch are same-host polling from
`UpstreamDegradedBanner.tsx:136` and `notificationsClient.ts:51-54` — correlated with the 503, not causal.
The tester's inference was reasonable from the outside; it was wrong.

**The real mechanism is in the deployment pipeline, and it is documented in the workflow's own comments.**
`.github/workflows/azure-static-web-apps-purple-water-03205fa03.yml` defines:

```yaml
STAGING_SWA_URL:    https://purple-water-03205fa03.6.azurestaticapps.net
PRODUCTION_SWA_URL: https://purple-water-03205fa03.6.azurestaticapps.net
```

**They are the same hostname.** There is only one SWA environment. On every push to `main` that touches
`frontend/src`, the pipeline:

1. builds with `VITE_API_URL = STAGING_API_URL` and deploys that bundle to **the production hostname**
   (line 181, "Deploy staging bake to SWA (temporary — overwritten by prod bake)");
2. runs Playwright against it as a hard gate — a 30-second propagation sleep plus three spec files at
   `--workers=1`, so minutes, not seconds;
3. only then rebuilds with the production API and redeploys.

So the user-facing production URL knowingly serves a **staging-wired bundle** on every frontend deploy. And
if step 2 fails, step 3 never runs and **purple-water is left on the staging bake indefinitely**. That is
not my inference — the repository already has a job to recover from it:

```yaml
# EMERGENCY PRODUCTION BAKE (workflow_dispatch only)
# Restores tip==LIVE when a staging bake was left on purple-water after a
# failed staging_ui_verification gate.
```

This explains every observation in PX-178: two backends, genuinely different data (129 risks vs 0), tokens
not valid across both, and no UI indication — because from the client's point of view nothing switched; it
was handed a different bundle.

**Reclassification.** PX-178 stays P0. It is not a frontend defect and it is not "misconfiguration" — it is
a deliberate design that trades production integrity for a verification shortcut. Fix: give the staging bake
its own SWA named preview environment (`deployment_environment:` on the deploy action) so the production
default environment is never overwritten. Owner is CI/CD, not frontend. Delete "locate the health-check
fallback" from the work order.

**PX-191 is the same event.** "Frontend build changed mid-run" is graded P3 and treated as a test-hygiene
annoyance. It is the observable side of this P0. See §4.1 for the timing evidence.

### 2.2 §3.1 / PX-255 — the shared scoring layer does not exist

**The work order says** four modules share a scoring layer in which "unassessed items default to a passing
value, are excluded from the denominator, or are seeded with placeholder scores", and prescribes one fix:
add an `assessed: bool` to the scoring model and make aggregation refuse to average over unassessed rows.

**There is no shared layer.** Three independent implementations, three different causes. The prescribed fix
resolves one of the three.

**PX-255 (UVDB) — partly confirmed, mechanism wrong.** The empty sections are real: sections 3–11 carry
`max_score: 0` and `questions: []` (`src/domain/uvdb/protocol_b2_v118.py:203-210`). But the 93–100% figures
are **not computed from question scoring at all**. They are OCR/regex extractions from the audit PDF's own
section breakdown, converted at import time:

```
src/domain/services/external_audit_analysis_service.py:924-933   pct = round((score / max_score) * 100, 1)
src/api/routes/uvdb.py:565-605                                   reads UVDBAudit.section_scores
frontend/src/pages/UVDBAudits.tsx:1500-1551                      renders scoreData.percentage regardless of content_status
```

"93%" means *the PDF said 14/15*. It does not mean "zero questions scored as compliant". This is a **display
gating** defect: imported per-section scores are shown against protocol sections whose questions were never
loaded, with no cross-check between the two pipelines. Adding `assessed: bool` to a scoring model would not
change the rendered number by one percentage point. The correct fix is to refuse to render an imported
section score where `content_status == "pending_protocol_pdf"`, and to exclude those sections from the
headline average — which the frontend already does for `max_score` (`UVDBAudits.tsx:839-842`) and simply
fails to do for `percentage`.

**PX-216 (audit analytics) — confirmed, and this one *is* the empty-denominator bug:**

```
src/domain/services/audit_analytics_service.py:211-212
    essential_compliance_pct = (1 - (essential_failed / essential_total)) * 100 if essential_total else 100.0
```

Zero essential responses yields **100.0%**, rendered beside a 95.8% fail rate computed from a completely
different population (run-level `AuditRun.passed`). The "nice work" message is a *third* metric again — it
scans only *active* runs (`:464-472`), so an empty queue means "nothing in flight", not "nothing failing".
Three unrelated numbers presented as one picture.

**This anti-pattern is more widespread than the pack reports, just not where it says.** `if total else 100.0`
also appears at `audit_analytics_service.py:392`, `executive_dashboard.py:359,462,486`, `vehicles.py:138`
and `slo.py:98`. That is the genuinely systemic finding hiding underneath §3.1, and it is worth a codebase
sweep — but PX-255 is not one of its instances.

**PX-234 (ISO) — partly confirmed, and the alarming reading is wrong.** `fallback` does not mean
"invented percentages". It means no canonical `Standard` row exists in the tenant database
(`src/api/routes/compliance.py:759`), so the module computes against an embedded clause catalogue instead.
The percentages are real evidence-link arithmetic over that catalogue
(`iso_compliance_service.py:3029-3075`), not seeded demo values. Still misleading to a client — a percentage
computed against a catalogue the organisation never adopted — but it is a labelling and data-configuration
problem, not fabrication.

**Consequence for the plan:** §3.1 currently scopes one fix and claims four defects. Scope **three**: a UVDB
display gate, an empty-denominator sweep, and an ISO standards-configuration task. Keep the required
outcome — an unassessed item must score zero or be excluded with the exclusion stated on screen — it is
exactly right. Only the diagnosis is wrong.

### 2.3 PX-248 — confirmed, and it is not an AI governance problem

**The work order treats this as AI governance** (GROUP 8): "Copilot must read live data or honestly refuse
— never synthesise", plus DPIA and lawful-basis work.

**There is no AI in the Copilot.** Both tiers are hardcoded stubs. The exact strings the tester reported as
fabrications are literals in the source:

```
frontend/src/components/copilot/AICopilot.tsx:232-235   "Supply Chain Disruption (Score: 20)", "Cybersecurity Threat"
frontend/src/components/copilot/AICopilot.tsx:225-226   "Overall Compliance: **92%**"
src/domain/services/copilot_service.py:365-367          "For now, we'll use pattern matching for demo" -> _simulate_ai_response
src/domain/services/copilot_service.py:420-443          the same two risk names, server-side
```

And PX-250's false "Action completed" is a timer, with a fabricated reference:

```
frontend/src/components/copilot/AICopilot.tsx:258-272   sets actionStatus 'completed' after a 500ms sleep, no API call
src/domain/services/copilot_service.py:535-541          returns "incident_id": "INC-2026-0100"   # Would create actual incident
```

It is mounted globally in production at `frontend/src/components/Layout.tsx:672-678`.

**This is better and worse than reported.** Better: no model is hallucinating, no data is being sent
anywhere, and the fix is to feature-flag the component off — hours, not a governance programme. Worse: a
demo stub shipped to a live statutory system, reachable from every screen, telling users compliance is 92%
and claiming to have filed safety records it never filed. The tester's P0 is fully justified.

**Consequence for the plan:** split GROUP 8. Copilot removal (PX-248, PX-250, PX-249) is Wave 0 and trivial.
The genuine AI governance work is **PX-285 only** — `/ai-intelligence`, which does name real third-party
processors and does describe a real pipeline over real case data. Do not let the easy fix ride on the hard
one; today they are bundled and the bundle will move at the speed of the DPIA.

---

## 3. PX-281 — root cause found

The pack correctly withdrew the `workforce_roles` attribution and left this open. Here is the cause.

**A 20-character limit on a field the form fills with an email address.**

```
src/api/routes/employee_portal.py:105          reporter_phone: Optional[str] = Field(None, max_length=20)
frontend/src/pages/PortalDynamicForm.tsx:934   reporter_phone: formData.complainant_contact ? String(...) : undefined
frontend/src/pages/PortalDynamicForm.tsx:475   name: 'complainant_contact', label: 'Contact Details',
                                               is_required: true, placeholder: 'Phone or email'
```

The complaint form has a required "Contact Details" field whose placeholder **invites an email address**.
That value is mapped to `reporter_phone`, which Pydantic caps at 20 characters. Any realistic work email —
`john.smith@plantexpand.co.uk` is 28 — fails validation with HTTP 422 before the handler is reached. The
tester's own evidence fits: unrecoverable, because retyping the same contact detail reproduces it exactly.

**Why near-miss submits successfully with the identical roles banner:** the near-miss template has no contact
field at all, so it never populates `reporter_phone`. The tester's withdrawal was correct and their reasoning
was sound — the banner genuinely is a red herring.

**Fix (frontend, one place):** in `handleSubmit`, route an email-shaped `complainant_contact` to
`reporter_email` and only map to `reporter_phone` when it looks like a phone number of 20 characters or
fewer. Raising the backend limit instead would store emails in a phone column; do that only as a hotfix.

**This is a ten-line fix to a P0 dead journey.** It belongs in Wave 1 alongside PX-315, and it is smaller
than either.

---

## 4. What the run could not see

### 4.1 The tested build, and what it means

Build `ddfed003` is real and traceable: commit `ddfed003`, "feat(complaints): raise Enterprise Risk from
complaint detail (SYS-04) (#1277)", authored 09:24:29Z on 25 July. The register records the build at
09:29:25Z — five minutes later. The environment statement is accurate.

**Eleven commits landed on `main` after that build, all on the same day, between 12:01Z and 21:06Z — during
and after the run.** Exactly **one** of them touched `frontend/src` and therefore triggered a frontend
redeploy: **#1282 at 12:01Z** ("governance list columns, author/live_at API, campaign ring").

That single event is the corroboration for two defects:

- **PX-191** ("frontend build changed mid-run", P3) — confirmed, with a timestamp.
- **PX-178** — a frontend deploy at 12:01Z is precisely when the pipeline in §2.1 places a staging-baked
  bundle on the production hostname. The tester's session spanned it: their portal evidence carries
  timestamps from 16:27Z to 19:49Z, and the complaint draft they found destroyed was created at 16:27:38Z.

The other ten commits were backend and infrastructure, so they did not alter the tested UI — but they do
mean **some findings may already be stale**, and the re-test should not assume otherwise:

| Merged | PR | Bears on |
|---|---|---|
| 12:35Z | #1281 unstick indexing + semantic search 404 | **PX-220** (Library search returns everything) and PX-185 (withdrawn as "transient indexing") — check both before re-testing |
| 13:01Z | #1282 governance list columns | Library list UI as tested |
| 16:55Z | #1285 Celery event-loop reuse | background task reliability |
| 17:30Z–18:43Z | #1286, #1287, #1288 deploy gates | the staging→production promotion gate itself |
| 20:08Z–21:06Z | #1289, #1290, #1291 Pinecone lifecycle, worker log sink | search-result integrity, diagnosability |

**PX-220 is the one to re-check first.** #1281 was specifically a Library indexing and semantic-search fix
and it merged an hour after the tested build.

### 4.2 The 503s have an infrastructure explanation

PX-170 (permanent skeleton after a failed fetch) and PX-171 (intermittent 503 on the incident detail
endpoint, ~50s) are both graded on their symptoms. The underlying cause is almost certainly hosting, and it
is documented separately in **ADR-0019**: all six App Services — production API, worker and beat, *and* the
three staging equivalents — run on **one Basic B2 App Service Plan, single instance, 2 vCPU, in West
Europe**, while the database and Redis are in **UK South**. Production competes with staging for two cores,
every query crosses regions, and Basic tier has no deployment slots so deploys restart in place.

A ~50-second timeout on a single record fetch is what CPU starvation looks like from a browser. PX-170's
**frontend** defect is real and independent — the error is caught, logged and never rendered
(`IncidentDetail/loadIncident: timeout of 30000ms exceeded`) — and must still be fixed. But do not expect
GROUP 6 to stop the 503s; that needs the hosting change.

### 4.3 A test suite that passes while the journey is dead

PX-315 deserves a note beyond its fix. The endpoint requires an HMAC `tracking_code`:

```
src/api/routes/employee_portal.py:1101-1118   track_report(reference_number, ..., tracking_code=Query(None))
src/api/routes/employee_portal.py:263-268     validate_tracking_code() -> False when the code is missing
frontend/src/pages/PortalTrack.tsx:350-351    sends neither tracking_code nor an Authorization header
```

The forms **already store** the tracking code (`PortalDynamicForm.tsx:955-956`), and the Track page never
reads it. So the tester's hypothesis — a lookup-column or tenancy mismatch — was wrong; the detail endpoint
is an anonymous, code-gated route that the authenticated UI calls as if it were a session route. The 404 is
returned before any database access, which is why all six references failed identically.

And the E2E test passes because it does what the UI does not:

```
tests/e2e/test_portal_e2e.py:199-201   detail call includes params={"tracking_code": tracking_code}
```

A green suite over a dead journey. Worth a broader look at whether portal E2E tests exercise the client's
actual call signatures.

---

## 5. Findings confirmed — with a cheaper fix than scoped

Six findings are confirmed but the work order overstates the work. In each case a mechanism already exists.

| Finding | Work order scopes | Actually |
|---|---|---|
| **PX-155** (P0, audit trail) | "immutable append-only audit logging across all modules" — greenfield | **Already built.** `audit_log_entries` table, `AuditLogService`, and `/api/v1/audit-trail` all exist. There are **73** `record_audit_event()` call sites and only **14** pass `tenant_id`; the rest hit `audit_service.py:242-332`, log a warning and **return without writing a row**. `log_auth()` exists at `audit_log_service.py:221-237` with **zero callers** — login never calls it. Fix is wiring, not construction |
| **PX-141 / PX-142** | part of the audit-trail build | Separate mechanism entirely: investigations use `investigation_revision_events`. PX-141 is a missing `create_revision_event()` on the PATCH close path (`investigations.py:806-890`). PX-142 is a missing user join — the timeline renders `actor_id` through `"Actor #{{id}}"` (`InvestigationTimeline.tsx:204-207`, `en.json:1794`). The actor **is** available at the write site |
| **PX-312** (P0, anonymity) | "materially larger: an anonymity flag on the report model, suppression through every downstream view…" | **The backend already supports it.** `is_anonymous` is accepted (`employee_portal.py:108`), suppresses the name (`:137`) and the email (`:417`), and HMAC tracking codes already exist (`:246-268`). All four forms hardcode `is_anonymous: false`. The tester searched frontend bundles only — a fair limitation, but it makes "build it" much cheaper than stated. Removing the promise is ~15 lines in `PortalHelp.tsx` (2 FAQ entries at `:159-169`, one category card at `:121-127` — which advertises `count: 5` for 2 entries, itself a small defect) |
| **PX-300** (P1, drafts) | "nothing ever reads it back" | A read path **does** exist — but it is gated on `Object.keys(initialData).length === 0` (`DynamicFormRenderer.tsx:610-615`), and `PortalDynamicForm` always passes 3–5 prefilled keys (`:868-881`), so the prompt can never appear. One condition, not a feature. The destructive overwrite is confirmed exactly as described |
| **PX-168** (P0, assignment) | `INVESTIGATE` whether bulk linking is possible | **It exists** (`Engineers.tsx:294-306`). And assignment genuinely requires a login: the FKs target `users.id` (`investigation.py:278`, `capa.py:91`, `risk_register.py:154`), so the picker is correct to disable unlinked employees. This is a **data task**, not a schema change. PAMS auto-links only on exact email match (`pams_technician_sync_service.py:142-157`) — that is why 82 of 84 are unlinked |
| **PX-121** (P1, publish guard) | "block publishing a form whose required field maps to an empty lookup" | Correct, and **the pattern already exists** — audit templates have `_validate_publishable_template()`, while `form_config_service.py:236-264` only flips a flag |

**PX-320** is confirmed as stated (`derive_clear_state()` at `portal_compliance_service.py:57-70` returns
`"clear"` on all-zero input and never inspects `no_tools` / `no_van`) — with one trap: a unit test at
`tests/unit/test_portal_compliance_service.py:89-90` **asserts the current behaviour**. Fixing the defect
requires changing a test that presently locks it in. Worth knowing before someone treats the red test as a
regression.

---

## 6. Two corrections that change scope, not severity

**PX-119 / PX-120 — the lookup values document is aimed partly at categories the portal never reads.**
The admin UI lists eight categories (`LookupTables.tsx:33-42`), but the portal forms request only three:
`customers`, `workforce_roles`, `medical_assistance`. Configuring `incident_types`, `complaint_types`,
`severity_levels` and `emergency_services` is worth doing — the admin modal and downstream classification
need them — but it will not change the portal forms. Only **`workforce_roles`** unblocks PX-119, via the
required `person_role` select at `PortalDynamicForm.tsx:137-144`.

There is also a naming trap: the legacy seed created category **`roles`** (migration `20260120`), while the
portal reads **`workforce_roles`**. Migration `20260806` copies one to the other *only if the legacy rows
exist*. A tenant with neither ends up with an empty `workforce_roles` even after migrating — which is
consistent with what production shows. `incident_types` and `complaint_types` have no seed at all.

**PX-306 — the 404 is missing data, not a wrong route.** The path and slugs are correct
(`api/__init__.py:193`, `form_config.py:214-231`). No migration ever seeds the four portal templates, and
`is_published` defaults to `false` (`alembic/versions/20260120_add_form_config_tables.py`). The tester's
alternative hypotheses (prefix wrong, underscore-vs-hyphen) are both refuted. Note this compounds PX-272:
the Form Builder is empty *and* nothing seeds it, so the forms in service can never be the forms an
administrator manages.

**PX-327 is worse on the shipped route than the pack realised.** Confirmed in full: files are appended to
React state (`DynamicFormRenderer.tsx:450-472`) and the submit body is `JSON.stringify`d
(`PortalDynamicForm.tsx:55-59`), so `File` objects serialise to `{}` and `attachment_ids` is never sent.
The backend *can* link attachments, but only by ID via `resolve_portal_attachment_assets`
(`employee_portal.py:884-886`), and the only upload endpoint requires the `evidence:create` permission
(`evidence_assets.py:172-176`) which a portal user does not hold — so there is **no route by which the
portal could upload a file today**. The legacy static forms at least converted photos to filename metadata;
the shipped dynamic path drops that too. Backend size and type limits exist (50 MB, content-type allowlist)
but are unreachable from the portal, which is why PX-325 finds none.

**PX-282 and PX-329 share one root cause.** Both come from `AnimatePresence mode="wait"` in
`DynamicFormRenderer.tsx:825-832`: the stepper, progress bar and button label key off `currentStep`
immediately while the body waits for an rAF-driven exit animation. In a foreground tab that is the
two-click desync (PX-282); in a backgrounded tab rAF stops and the incoming step never mounts at all
(PX-329). The RTA form uses plain conditional rendering and has neither defect — so the fix is to
**converge on the working pattern**, and it closes a P1 and a P2 together.

---

## 7. Corrected delivery sequence

Changes from the work order are marked. Everything else stands.

| Wave | Contents | Change |
|---|---|---|
| **0 — hours** | Feature-flag the Copilot off (PX-248, PX-250, PX-249). Block `/ai-intelligence` pending DPIA (PX-285). Remove the Superuser smoke account (PX-197). | **Split from GROUP 8.** Copilot is a stub, not an AI governance item — do not let it wait on the DPIA |
| **0.5 — hours** | **Restore the production API bake on purple-water and confirm it is serving it.** Then give the staging bake its own SWA environment (PX-178). | **New, and first.** Until this is done, every frontend fix below can be silently replaced by a staging-wired bundle. Check current state before anything else |
| **1 — days** | PX-315 (send the tracking code / accept the session). **PX-281 (route the email to `reporter_email`)**. **PX-327 (build the portal upload path)**. PX-312 (decide, then remove or ship). `workforce_roles` lookup (PX-119). Bulk-link employees (PX-168). | **PX-281 and PX-327 added.** PX-327 was absent from Wave 1 despite the work order calling it the highest-value fix in the document. PX-281 is now a known ten-line fix to a dead P0 journey |
| **2 — weeks** | Wire the existing audit log (PX-155, PX-141, PX-142). GROUP 2 closure gates. GROUP 6 error states. GROUP 4 void/archive. PX-300 draft hydration. **PX-282 + PX-329 together** via the stepper convergence. | PX-155 is wiring, not construction. PX-282/PX-329 merged into one item |
| **3** | GROUP 3 responsive tables. GROUP 5 search — **re-verify PX-220 against current `main` first (#1281)**. GROUP 7 single source of truth per metric. | PX-220 may already be fixed |
| **4** | **UVDB display gate (PX-255)**, **empty-denominator sweep (PX-216 + the five other sites)**, **ISO standards configuration (PX-234)** — three items, not one. Data cleanup §6. E1 enhancements. | §3.1 rescoped from one fix to three |
| **5** | E2 and E3 polish. | unchanged |
| **Separate track** | Hosting isolation and region consolidation per ADR-0019 — the likely cause of PX-170/PX-171 and the 5-minute deploy outages. | **New.** Already written up and awaiting review |

---

## 8. Re-test preconditions — amended

The pack's six conditions all stand. Add three:

7. **Evidence of which bundle purple-water is serving**, captured at the start and end of the run — the
   inlined `VITE_API_URL` and the service-worker `CACHE_VERSION`. Run 021's most severe finding was
   invisible from inside the application, and this is the cheapest way to make it visible.
8. **A frozen `main`, or an announced deploy window,** for the duration of the run. One frontend merge
   landed mid-run and produced two defects.
9. **The test-residue list reconciled.** The three lists in the pack disagree: the README and register name
   nine records including two near-misses; the work order §6 names ten including `RTA-2026-0032`,
   `AUD-2026-0083` and `FND-2026-0204` but **omits both near-misses** — including
   `NM-2026-6D3DE96F`, which is the evidence record for PX-327. Combined, thirteen records need deleting.
   Since this is a manual data task on production with no UI delete (PX-177), an incomplete list means
   residue survives into the re-test.

---

## 9. Summary of verification results

| Finding | Sev | Symptom | Mechanism as diagnosed | Action |
|---|---|---|---|---|
| PX-119 / PX-120 | P0 | confirmed | partly — only `workforce_roles` blocks the portal | rescope the lookup task |
| PX-155 | P0 | confirmed | **wrong scope** — mechanism exists, 59 of 73 hooks unwired | rescope: wiring |
| PX-168 | P0 | confirmed | confirmed; bulk link already exists | data task |
| PX-178 | P0 | confirmed | **refuted** — CI/CD, not frontend failover | reassign + Wave 0.5 |
| PX-248 | P0 | confirmed | **refuted** — hardcoded stub, no AI | Wave 0, split from GROUP 8 |
| PX-255 | P0 | confirmed | **refuted** — imported PDF scores, no shared layer | rescope §3.1 to three fixes |
| PX-281 | P0 | confirmed | **was unknown — now found** (`reporter_phone` max_length 20) | Wave 1, ten lines |
| PX-312 | P0 | confirmed | partly — backend support already exists | cheaper either way |
| PX-315 | P0 | confirmed | **refuted** — anonymous tracking gate, not a lookup mismatch | Wave 1, smaller than scoped |
| PX-327 | P0 | confirmed | confirmed, and worse — no upload route exists at all | **promote into Wave 1** |
| PX-320 | P1 | confirmed | confirmed | note the test that locks it in |
| PX-300 | P1 | confirmed | partly — read path exists but is gated off | one condition |
| PX-282 / PX-329 | P1 / P2 | confirmed | confirmed, shared cause | fix as one |
| PX-306 | P2 | confirmed | partly — missing seed, route is correct | data + optional banner |
| PX-325 / PX-326 | P2 / P3 | confirmed | confirmed | depends on PX-327 |
| PX-216 | P1 | confirmed | confirmed — and five more sites | sweep |
| PX-234 | P1 | confirmed | partly — real arithmetic over a static catalogue | relabel + configure |
| PX-171 / PX-170 | P2 / P1 | confirmed | frontend half real; 503s are hosting | ADR-0019 |
| PX-191 | P3 | confirmed | same event as PX-178 | link to PX-178 |

**Nothing in the register was found to be fabricated, and no severity was found to be inflated.** Of the
eleven P0s, all eleven have a real defect behind them. Four had the wrong mechanism, and that is the normal
and expected limit of black-box testing — it is exactly what Phase B exists to catch.
