# Change Ledger (CL-RUN021-LANE4-AUDITS-UVDB-ASSURANCE)

## 1) Summary
- **Feature / Change name:** Run021 Wave-next Lane 4 — Audits + UVDB + Assurance residual honesty
- **User goal:** Assurance operators see consistent programme counts, honest empty states, a single UVDB control chrome, and schedule/library views that do not present Playwright fixtures as real templates.
- **In scope:** PX-256, PX-259, PX-245, PX-258, PX-219, PX-266, PX-243, PX-255 residual (average provenance label). PX-242 / PX-261 verified already on main (#1315) — evidence only.
- **Out of scope / residual:** Full UVDB scoring-engine rewrite for empty sections; certificate data seeding; hard-delete of fixture templates; Analytics/Dashboard/Compliance; Portal/Investigations/Actions; i18n files; employeePickerUtils; Admin/Docs bulk refactors.
- **Feature flag / kill switch:** None — revert this PR.

## 2) Impact Map (what changed)
- **UVDB:** Remove duplicate section select+Filter; keep single tab row + global audit filters; protocol vs Audits-board Achilles alignment strip; average KPI provenance caption.
- **Customer Audits:** Cross-programme honesty when customer slice is empty but Achilles/Planet Mark runs exist on the board.
- **Audits schedule:** Hide Playwright / CUJ / UAT fixtures from schedule template picker with honesty hint.
- **Template library:** Default-hide automation fixtures + reveal toggle + fixture badge.
- **Certificate shelf:** Distinct empty copy for filtered vs unpopulated shelf.
- **Helpers / tests:** `auditTemplateHonesty`, `uvdbHelpers`, `customerAuditsHelpers`, `assuranceCertShelfHelpers` + vitest coverage.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive presentation / filter honesty only — no schema migrations, no i18n key edits.
- **Breaking changes:** None.
- **Rollback strategy:** Revert squash merge / redeploy prior SHA.

## 4) Acceptance Criteria (AC)
- [x] AC-01 (PX-258): UVDB has one section tab row; no duplicate select+Filter chrome.
- [x] AC-02 (PX-256): UVDB scores show protocol count vs Audits board Achilles count with disagreement honesty + deep-link.
- [x] AC-03 (PX-255 residual): Average KPI caption distinguishes imported / mixed / calculated / not scored.
- [x] AC-04 (PX-259 / PX-245): Customer programme empty state explains sibling Achilles/Planet Mark runs on the board.
- [x] AC-05 (PX-219): Schedule Audit picker excludes automation fixtures and states how many were hidden.
- [x] AC-06 (PX-266): Template library hides fixtures by default; reveal shows “automation fixture” badge.
- [x] AC-07 (PX-243): Certificate shelf empty distinguishes filter miss vs unpopulated shelf.
- [x] AC-08 (PX-242 / PX-261): Regression suites still green (evidence on main).

## 5) Testing Evidence
- [x] Vitest targeted suites — **74/74 passed** (local)
- [ ] Full CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/uvdb` scores — protocol vs board strip when counts disagree.
- [x] CUJ-02: `/customer-audits` — empty customer + Achilles/Planet Mark honesty strip.
- [x] CUJ-03: Schedule Audit — CUJ-AT / Playwright templates absent from picker.
- [x] CUJ-04: `/audit-templates` — fixtures hidden by default; toggle reveals badge.
- [x] CUJ-05: `/assurance/certificates` — filtered empty ≠ unpopulated empty.

## 7) Observability & Ops
- **Logs / metrics / alerts:** None new.

## 8) Release Plan
- **Staging:** Spot-check UVDB alignment strip, customer empty honesty, schedule picker, template fixture toggle, cert shelf filter empty.
- **Prod post-deploy:** Same five surfaces.

## 9) Rollback Plan
- **Trigger:** Wrong programme counts, schedule missing real templates, UVDB chrome regression.
- **Steps:** Revert PR; redeploy prior SHA.

## 10) Evidence Pack
- CI run(s): (filled by CI on this PR)
- Base branch: `main`
- Continues after #1336 (does not re-claim PX-257/260/262/265)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Lane 4 allowlist respected (Audits*/UVDB*/Assurance*/audit-builder* related only; no en/cy; no Portal/Investigations/Actions/registers/Analytics)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 5:** Production verification plan ready

## Defects addressed

| ID | This PR |
|---|---|
| **PX-256** | Protocol vs Audits board Achilles count/score honesty strip + average provenance |
| **PX-259** | Customer empty explains sibling external programmes on Audits board |
| **PX-245** | Same cross-programme honesty for empty customer shell |
| **PX-258** | Remove duplicate UVDB section select+Filter; keep tabs + global filters |
| **PX-219** | Hide automation fixtures from Schedule Audit picker |
| **PX-266** | Template library default-hide fixtures + badge when revealed |
| **PX-243** | Cert shelf filtered vs unpopulated empty copy |
| **PX-255** | Residual — label imported/mixed averages (not a scoring-engine rewrite) |
| **PX-242** | **Evidence** — already on main (#1315); regression green |
| **PX-261** | **Evidence** — already on main (#1315); regression green |

| ID | Residual / deferred |
|---|---|
| **PX-255** | Engine still stores imported empty-section scores — needs protocol ingest / scoring policy lane |
| **PX-244** | Sections 3–11 PDF ingest still pending — structural content lane |
| **PX-219 / PX-266** | Ops cleanup to unpublish/archive fixtures in data — not hard-deleted here |
| **PX-243** | Seeding real certificates — data/ops lane |

## Test plan
- [x] `cd frontend && npx vitest run` (targeted): auditTemplateHonesty, uvdbHelpers, customerAuditsHelpers, assuranceCertShelfHelpers, UVDBAudits, CustomerAudits, AssuranceCertShelf, AuditTemplateLibrary, Audits.formPrimitive, AuditExecution.answerHighlight
- [ ] Staging: UVDB disagree strip; customer empty honesty; schedule without CUJ fixtures; cert shelf filter empty

Made with [Cursor](https://cursor.com)
