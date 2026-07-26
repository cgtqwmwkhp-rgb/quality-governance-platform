# Change Ledger (CL-RUN021-CASE-REGISTERS-RESIDUAL-B)

## 1) Summary
- **Feature / Change name:** Run021 Wave-next — Case registers residual slice B
- **User goal:** Controllers see chronological Occurred/Received order matching the date column, consistent Collision/Severity vocabulary, no fake `#surrogate` references, honest mixed-reference and missing-SLA notices — without claiming data cleanup or schema work that is not done.
- **In scope:** PX-124, PX-126 (honesty banner only), PX-154, PX-174, PX-209, PX-210 (honesty notice only); shared `caseRegisterHonesty` helpers; en/cy keys owned by this lane
- **Out of scope / residual:** PX-125 / PX-192 (ops test-data cleanup); PX-131 (admin lookup copy — admin lane); PX-126 minting remint (data lane — banner only here); PX-210 response-due schema (schema lane — notice only here); PX-292 HTML sanitisation (backend `nh3`)
- **Feature flag / kill switch:** None — revert this PR

## 2) Impact Map (what changed)
- **Shared:** `caseRegisterHonesty.ts` (+ tests); `CaseRegisterReferenceLink` optional `title`
- **Registers:** Incidents / Complaints / NearMisses / RTAs — client sort by displayed date; Incidents mixed-ref banner; Complaints Severity column header
- **Detail:** Incident / Complaint / NearMiss / RTA — breadcrumbs and linked asset/contract/risk labels hide `#id`; ComplaintDetail SLA-not-configured notice
- **i18n:** `en.json` / `cy.json` — RTA Collision wording + honesty copy keys
- **Tests:** vitest for honesty helpers, Incidents PX-124/126, IncidentDetail PX-174, ComplaintDetail PX-210

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Display / ordering / copy only; API payloads and reference minting unchanged; complaint `priority` field name unchanged (header/label only)
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy:** Revert merge / redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] **AC-01 (PX-124):** Visible incidents page ordered by Occurred (`incident_date`) newest first
- [x] **AC-02 (PX-126):** Mixed sequential + hex references on a page show an honesty banner; hex refs titled as legacy
- [x] **AC-03 (PX-154):** `/rtas` H1 and dialog copy use Collision (not Accident) in en + cy
- [x] **AC-04 (PX-174):** Detail breadcrumbs and linked asset/contract/risk chrome do not render `#${id}` / `Asset #N` / `Risk #N` / `Contract #N`
- [x] **AC-05 (PX-209):** Complaints register column header reads Severity (aligned with incidents/RTAs)
- [x] **AC-06 (PX-210):** Complaint detail shows persistent “No response SLA on this record” honesty notice

## 5) Testing Evidence
- [x] `cd frontend && npx vitest run` (targeted): caseRegisterHonesty, CaseRegisterReferenceLink, Incidents, IncidentDetail, ComplaintDetail, RTADetail — **73/73 passed** (local)
- [x] `node scripts/i18n-check.mjs` (local)
- [ ] Full CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** `/incidents` — Occurred column newest-first on the loaded page; mixed hex+sequential shows banner
- [x] **CUJ-02:** `/rtas` — page title “Road Traffic Collisions”
- [x] **CUJ-03:** `/incidents/:id` — breadcrumb shows reference; linked asset/risk/contract never show bare `#N`
- [x] **CUJ-04:** `/complaints` — Severity column header; `/complaints/:id` — SLA-not-configured notice visible
- [x] **CUJ-05:** `/near-misses` and `/complaints` lists still open rows after client sort

## 7) Observability & Ops
- **Logs / metrics / alerts:** None new
- **Ops note:** PX-125/192 still need production test-data cleanup; PX-126 remint remains a data/minting follow-up

## 8) Release Plan
- **Staging:** Spot-check `/incidents` sort + mixed-ref banner (if fixtures present), `/rtas` title, complaint Severity + SLA notice, one incident detail without `#id` chrome
- **Canary plan:** Standard staging → production train
- **Prod post-deploy:** Same four surfaces

## 9) Rollback Plan
- **Trigger:** Register order confusing controllers; Severity label wrong for complaint domain stakeholders; missing-SLA banner mistaken for an outage
- **Steps:** Revert this PR; redeploy prior SHA
- **Owner:** Platform / QGP maintainers (Lane 5 case-registers)

## 10) Evidence Pack
- CI run(s): (filled by CI on this PR)
- Base branch: `main` @ `59703b`
- File-disjoint from open #1345 (admin) and #1346 (analytics)
- Staging deploy evidence: (post-merge)
- Canary evidence: n/a

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Lane 5 allowlist respected (case registers + en/cy only; no Portal*/Investigation*/Actions*/Analytics*/Dashboard*/Admin*/employeePickerUtils)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary healthy (if used) — n/a, full promote
- [x] **Gate 5:** Production verification plan ready

## Defects addressed

| ID | This PR |
|---|---|
| **PX-124** | Client-sort registers by the date column controllers read (Occurred / Received / collision date) |
| **PX-126** | Honesty banner + legacy hex `title` when formats mix (minting remint residual) |
| **PX-154** | RTA register/dialog copy → Collision (en + cy) |
| **PX-174** | Hide surrogate `#id` / `Asset #N` / `Risk #N` / `Contract #N` on case detail chrome |
| **PX-209** | Complaints register + complaint field labels use Severity |
| **PX-210** | Persistent “No response SLA” honesty notice (schema residual) |

| ID | Residual / deferred |
|---|---|
| **PX-125** | Incident test-data cleanup — ops/data |
| **PX-192** | Complaints test-data cleanup — ops/data |
| **PX-131** | Admin lookup copy — admin lane (#1345) |
| **PX-126 remint** | Dual format minting — data lane |
| **PX-210 schema** | response-due / SLA columns — schema lane |
| **PX-292** | HTML strip vs escape — backend sanitisation |

## Test plan
- [x] Vitest targeted suites (see §5)
- [ ] Staging: `/incidents` sort; `/rtas` Collision title; complaint Severity + SLA notice; incident detail no `#id`
