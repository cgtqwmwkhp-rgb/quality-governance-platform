# Change Ledger (CL-FR-ASSIST-DEPTH-01)

> Base: `origin/main` @ `a7b5565c8` (#1592 GHA deps tip).
> Slice A1+A2+A3+A5 first (+ Markdown export). Does **not** touch `Layout.tsx` (#1715 owns Layout).

## 1) Summary

- **Feature / Change name:** FR-ASSIST-DEPTH-01 — deeper PlantEx Assist fact packs, SoR deeplinks, transcript export
- **User goal (1–2 lines):** Follow-ups that registers already answer (closed counts, injury / back / manual-handling categories) must resolve from computed figures instead of refusing; every quoted ref links to its SoR row; chat can be exported as Markdown with absolute deeplinks.
- **Problem:** After “how many incidents…”, Assist refused “how many are closed?” and “back injuries or manual handling?” because the fact pack was a single total with no status/injury dims. Answers were one-line and refs were not navigable.
- **In scope:**
  - Expand closed grounded intents: `incident_closed_count`, `incident_injury_category`
  - Enrich incident fact pack with status / injury / MH (manual handling) / type breakdowns + markdown tables
  - SoR deeplinks on every quoted ref (`[REF](/path)`); CopilotMarkdown renders safe in-app anchors
  - Markdown transcript export (absolute URLs); PDF deferred to print-from-Markdown
  - Honesty lock unchanged (figures-only · no writes · refuse outside fixed set)
- **Out of scope / deliberately not done:**
  - `Layout.tsx` / nav (owned by #1715)
  - Native PDF binary export (print-to-PDF from Markdown is the interim)
  - Broad open-chat / writes / new feature flags
  - Expanding near-miss / complaint depth packs beyond deeplink formatting on existing intents
- **Feature flag / kill switch:** Unchanged (`AI_COPILOT_ENABLED` / `AI_COPILOT_INFERENCE_ENABLED`).

## 2) Impact Map (what changed)

- **Frontend:** `AICopilot.tsx` (export control), `CopilotMarkdown.tsx` (deeplinks), `assistTranscriptExport.ts` (new), tests
- **Backend:** `copilot_grounding.py` — intents, deeper incident gatherer, invasive plain formatter, citation scrub for link paths
- **Tests:** `test_copilot_grounded_inference.py`, `test_copilot_grounded_compliance.py` (format/deeplink assertions)
- **APIs / schemas / database / flags:** None
- **Docs:** This Change Ledger

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive closed intents + richer fact packs. Existing intents keep working; reply shape gains bold counts, tables, and markdown links.
- **Breaking changes:** None for APIs. Deterministic grounded replies now use `**count**` and `[REF](/path)` — citation validator updated to ignore path-segment digits.
- **Migration plan:** N/A
- **Rollback strategy:** Revert merge commit; redeploy prior tip. No schema/flag/data.
- **PII:** No new personal data; MH match uses register title/description/body_parts text already stored on incidents.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Closed / injury / MH follow-ups | Refused (facts lacked dims) | Resolved from computed register figures |
| Citation honesty | Figures/refs fail-closed | Unchanged fail-closed; path ids scrubbed |
| Writes via Assist | Forbidden | Unchanged forbidden |
| Outside fixed set | Refuse | Unchanged refuse |
| SoR navigation from cited refs | Plain text refs | In-app deeplinks; absolute in export |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** “How many of those incidents are closed?” maps to `incident_closed_count` and answers from `status == closed` count.
- [x] **AC-02:** Back-injury / manual-handling follow-ups map to `incident_injury_category` and answer from computed body_parts / title-description matches (not invent).
- [x] **AC-03:** Generic incident count fact pack includes status + injury/MH + type breakdown tables.
- [x] **AC-04:** Every sample ref in deterministic replies is a markdown link to the SoR route (incident / near-miss / complaint / action / compliance-schedule).
- [x] **AC-05:** CopilotMarkdown renders safe in-app `/…` anchors and rejects `javascript:` / external schemes.
- [x] **AC-06:** Export control downloads Markdown with questions, answers, citations, and absolute deeplinks.
- [x] **AC-07:** Honesty lock unchanged — no create/edit/delete; out-of-set still refuses; AI words only over platform figures.
- [x] **AC-08:** `Layout.tsx` not modified.
- [x] **AC-09:** Change Ledger body present for `pnpm validate:pr-body` / gate checklist.
- [x] **AC-10:** No test skipped or loosened to go green.

## 5) Testing Evidence

Observed locally, not inferred:

- [x] `pytest tests/unit -k copilot` — **161 passed**, 0 failed
- [x] `npx vitest run src/components/copilot` — **37 passed**
- [x] `black` / `isort` / `flake8` on touched backend files — clean
- [ ] Full CI / staging / prod LIVE — after PR open; conveyor owns merge → tip LIVE

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Ask incident count → ask closed follow-up → grounded closed count with status table + deeplinked refs.
- [x] **CUJ-02:** Ask back injuries / manual handling follow-up → grounded injury/MH pack (not refuse).
- [x] **CUJ-03:** Export transcript → Markdown file with absolute `https://…/incidents/{id}` links.

## 7) Observability & Ops

- **Logs / metrics / alerts:** Existing citation-drop warning retained
- **Runbook:** N/A — Assist depth only

## 8) Release Plan

- Squash-merge to `main` only via conveyor allowlist → Main CI → Azure deploy → verify ACA image tip SHA + health on prod FQDN.
- **Do not merge from this PR author path** — leave for conveyor.

## 9) Rollback Plan

- **Trigger:** Wrong counts, invented figures, or unsafe links in Assist replies.
- **Steps:** Revert squash on `main`; redeploy prior tip via standard CD. Inference flags remain available as containment.
- **Owner:** Platform / conveyor

## 10) Evidence Pack

- CI / staging / prod tip: linked after merge and LIVE verify
- Local: copilot unit 161/161; frontend copilot vitest 37/37

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — grounded reply shape additive; API paths unchanged
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — flag-gated Assist)
- [x] **Gate 5:** Rollback = revert; flags unchanged
- [~] **UX Coverage Gate:** HOLD — ignored per conveyor instruction

## Shipped vs deferred

| ID | Outcome | This PR |
| --- | --- | --- |
| A1 Deep answers | Closed + injury/MH fact packs | Shipped |
| A2 Invasive tone | Breakdown tables + cite every figure | Shipped (deterministic path; LLM prompt updated) |
| A3 Deeplinks | SoR markdown links in-app | Shipped |
| A4 Export | Markdown transcript + absolute links | Shipped (Markdown); **PDF binary deferred** (print-to-PDF) |
| A5 Honesty lock | Figures-only · no writes · refuse outside set | Unchanged / locked |

Made with [Cursor](https://cursor.com)
