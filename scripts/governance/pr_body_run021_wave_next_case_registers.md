# Change Ledger (CL-RUN021-CASE-REGISTERS-WN)

## 1) Summary
- **Feature / Change name:** Run021 Wave-next — Case registers honesty (Lane 5)
- **User goal:** Controllers can open case rows via real links, see human labels and correct RTA nouns, save complaint field edits without a silent status-machine rejection, and distinguish driver from reporter on collisions.
- **In scope:** PX-206 (P1), PX-173, PX-200, PX-201, PX-202, PX-123; register label residuals on RTA/Complaints/Near Miss; sole-wave `en.json` / `cy.json` keys for RTA copy
- **Out of scope / residual:** PX-126 (mixed INC hex vs sequential refs — data/minting); PX-192 / PX-125 (test-data cleanup); PX-210 (complaint SLA / response-due schema); PX-131 (lookup admin copy); PX-127 / PX-204 / PX-148 already on main (evidence retained)
- **Feature flag / kill switch:** None — revert this PR

## 2) Impact Map (what changed)
- **Shared register:** `CaseRegisterTable` drops invalid `role="button"` on rows; new `CaseRegisterReferenceLink` for real `<a href>` references
- **Registers:** `Incidents`, `RTAs`, `Complaints`, `NearMisses` — reference links, title tooltips, coded-value badges; Complaints URL `priority` (reads legacy `severity`)
- **Detail:** `RTADetail` — “Audit this collision”, separate driver/reporter tiles, `Reported on {{date}}`, coded severity/status; `ComplaintDetail` — omit unchanged status on PATCH (PX-206)
- **Create:** New RTA modal captures independent `reporter_name` (session prefill)
- **i18n:** `en.json` / `cy.json` RTA reporter + audit + reported_on keys
- **Tests:** vitest for register links, PX-206 save payload, PX-201/202 RTA copy, PX-123 title tooltip

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive display/link behaviour; complaint PATCH omits unchanged `status` only; Complaints deep-links still accept legacy `?severity=`
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy:** Revert merge / redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] **AC-01 (PX-200):** RTA (and sibling) register references are real links with `href`
- [x] **AC-02 (PX-173):** Register rows are not `role="button"`; title/date clicks still open the case; Enter on focused row retained (PX-008)
- [x] **AC-03 (PX-201):** RTA header CTA reads “Audit this collision”
- [x] **AC-04 (PX-202):** RTA summary shows Driver and Reporter separately; create form captures reporter independently of driver
- [x] **AC-05 (PX-206):** Complaint field save with unchanged status does not send `status` in the PATCH body
- [x] **AC-06 (PX-123):** Clamped title cells expose full text via `title=`
- [x] **AC-07:** RTA/Complaints/Near Miss badges use `formatCodedValue`; RTA `reported_on` interpolates `{{date}}`

## 5) Testing Evidence
- [x] `cd frontend && npx vitest run` (targeted): CaseRegisterTable, CaseRegisterReferenceLink, Incidents, Complaints, ComplaintDetail, RTADetail, RTAs.formPrimitive, NearMisses.a11y, RTAs.a11y — **84/84 passed** (local)
- [ ] Full CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** `/incidents` — middle-clickable reference link; click title opens detail
- [x] **CUJ-02:** `/rtas` — reference is `<a href="/rtas/:id">`
- [x] **CUJ-03:** RTA detail — Audit this collision; Driver ≠ Reporter when both set
- [x] **CUJ-04:** Acknowledged complaint — edit resolution, save — succeeds without status no-op 409
- [x] **CUJ-05:** New RTA — reporter field present and session-prefilled when available

## 7) Observability & Ops
- **Logs / metrics / alerts:** None new

## 8) Release Plan
- **Staging:** Spot-check four registers’ reference links; RTA audit label; complaint edit-save on acknowledged row
- **Prod post-deploy:** Same three surfaces

## 9) Rollback Plan
- **Trigger:** Row navigation regression; complaint saves omitting status when status *did* change; RTA create missing reporter unexpectedly
- **Steps:** Revert PR; redeploy prior SHA

## 10) Evidence Pack
- CI run(s): (filled by CI on this PR)
- Base branch: `main`
- File-disjoint from open #1341 (portal) and #1342 (investigations/actions)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Lane 5 allowlist respected (case registers + en/cy only; no Portal*/Investigation*/Actions*/employeePickerUtils)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 5:** Production verification plan ready

## Defects addressed

| ID | This PR |
|---|---|
| **PX-206** | Omit unchanged `status` from complaint PATCH so field edits save |
| **PX-173** | Plain rows + whole-row click; no invalid `role="button"` |
| **PX-200** | Real reference `<Link href>` on all four case registers |
| **PX-201** | “Audit this collision” (en + cy) |
| **PX-202** | Separate driver/reporter display + create-form reporter field |
| **PX-123** | Full title via `title=` on clamped cells |
| Label residuals | RTA/Complaints/NM coded badges; RTA `Reported on {{date}}`; complaints URL `priority` |
| **PX-127** | **Evidence** — already on main (offline notice); tests retained |
| **PX-204** | **Evidence** — already on main (submit progress); tests retained |
| **PX-148** | **Evidence** — Details column already replaced on main |

| ID | Residual / deferred |
|---|---|
| **PX-126** | Dual INC reference formats — minting/data lane |
| **PX-192** | Complaints test-data cleanup — ops/data |
| **PX-210** | Complaint SLA / response-due — schema lane |
| **PX-131** | Admin lookups copy vs fallback — admin lane |

## Test plan
- [x] Vitest targeted suites (see §5)
- [ ] Staging: reference middle-click on `/rtas`; complaint acknowledged edit-save; RTA audit CTA wording

Made with [Cursor](https://cursor.com)
