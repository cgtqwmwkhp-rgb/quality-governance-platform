# Change Ledger (CL-RUN021-INV-ACTIONS-WN)

## 1) Summary
- **Feature / Change name:** Run021 Wave-next — Investigations + Actions assignee & closure honesty
- **User goal:** Investigators can assign lead investigators and CAPA owners from the active employee roster (including staff without portal logins), closure gates are enforced and surfaced honestly, and the Actions/CAPA surfaces show consistent references and filters.
- **In scope:** PX-168 (P0), PX-133, PX-169, PX-135, PX-150, PX-152, PX-233, PX-137, PX-138, PX-139, PX-140, PX-145, PX-276
- **Out of scope / residual:** **PX-136** (incident→investigation seeding — incidents module / data task); **PX-143** (branded PDF deliverable — JSON export + honest follow-on note already present in report helpers; full PDF rendering remains follow-on)
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend:** `InvestigationDetail.tsx`, `InvestigationActions.tsx`, `InvestigationHeader.tsx`, `InvestigationTimeline.tsx`, `Investigations.tsx`, `Actions.tsx`, `actionsDisplayHelpers.ts`, `employeePickerUtils.ts` (assignee resolution helper — documented for PX-168)
- **Backend:** `capa_service.py` (roster assignee marker), `investigations.py` (closure timestamps, entity reference hydration, completion gate on PATCH), `actions.py` (`sourceType=capa` filter + source reference hydration), `investigation_service.py` (`resolve_assigned_entity_reference`)
- **APIs:** `POST /investigations/{id}/capa` accepts `assignee_name`; investigation responses include `assigned_entity_reference`; `GET /actions?sourceType=capa` returns CAPA rows
- **Tests:** vitest helpers + pytest completion gate / CAPA roster assignee

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API fields; roster assignee stored as description marker when no `users.id` FK; existing CAPA rows unchanged
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge / redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] **AC-01 (PX-168):** Lead investigator + Add Action assignee pickers allow selecting active employees without portal login; roster name persisted and shown on action rows
- [x] **AC-02 (PX-169):** PATCH `status=completed|closed` rejects when closure checklist fails (existing gate retained; tests green)
- [x] **AC-03 (PX-133):** Investigations marked completed but failing checklist show an explicit invalid-completed banner (not silently closable)
- [x] **AC-04 (PX-135):** `started_at` captured on first transition into an active status (in progress / under review / completed / closed)
- [x] **AC-05 (PX-150):** `/capa` → `/actions?sourceType=capa` lists CAPA-backed actions (filter alias wired server-side)
- [x] **AC-06 (PX-152 / PX-233):** Actions list prefers hydrated `source_reference` (e.g. `REF-2026-0006`) over raw `investigation:6` keys
- [x] **AC-07 (PX-139):** Investigation header source chip uses `assigned_entity_reference` when available
- [x] **AC-08 (PX-140):** Investigations KPI board includes a Draft tile accounting for draft records
- [x] **AC-09 (PX-138):** Duplicate hand-off CTAs removed from workflow proof / summary (one open-source + one CAPA CTA remain)
- [x] **AC-10 (PX-137 / PX-276 / PX-145):** Engineer-facing PATCH/API copy replaced with operator defaults; timeline submit reads “Save entry”

## 5) Testing Evidence
- [x] `cd frontend && npx vitest run src/pages/workforce/employeePickerUtils.test.ts src/pages/__tests__/actionsDisplayHelpers.test.ts` — **10/10 passed** (local)
- [x] `python3.11 -m pytest tests/unit/test_investigation_completion_gate.py tests/unit/test_capa_source_investigation.py::test_create_capa_for_investigation_roster_assignee_without_login -q` — **6/6 passed** (local)
- [ ] Full CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Investigation → Add Action → pick roster-only employee → action created with assignee name visible
- [x] **CUJ-02:** Investigation → Summary → pick lead investigator without login → save summary → name persisted in `lead_investigator`
- [x] **CUJ-03:** Attempt complete with empty findings → blocked (toast + API 400)
- [x] **CUJ-04:** `/capa` redirect → filtered actions list shows CAPA rows
- [x] **CUJ-05:** Actions list source column shows case reference numbers not storage keys

## 7) Observability & Ops
- **Logs / metrics / alerts:** No new metrics; existing closure gate logs unchanged

## 8) Release Plan
- **Staging:** Spot-check assignee pickers, `/capa` filter, invalid-completed banner on legacy row, Draft KPI tile
- **Prod post-deploy:** Same four surfaces

## 9) Rollback Plan
- **Trigger:** Assignee marker parsing regression, CAPA filter empty, closure gate false positives
- **Steps:** Revert PR; redeploy prior SHA

## 10) Evidence Pack
- CI run(s): (filled by CI on this PR)
- Base branch: `main`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Investigations/actions allowlist respected (`employeePickerUtils.ts` touched for PX-168 assignee resolution — documented above)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 5:** Production verification plan ready

## Defects addressed

| ID | This PR |
|---|---|
| **PX-168** | Roster-selectable assignees; `assignee_name` API + description marker |
| **PX-133** | Invalid-completed banner when checklist still failing |
| **PX-169** | Verified enforced on main; tests retained |
| **PX-135** | `started_at` backfill on active status transitions |
| **PX-150** | `sourceType=capa` server filter |
| **PX-152** | Hydrated source references + display helper |
| **PX-233** | Same root cause as PX-152 |
| **PX-137** | Operator-facing copy defaults |
| **PX-138** | Removed duplicate hand-off controls |
| **PX-139** | `assigned_entity_reference` on investigation API + header chip |
| **PX-140** | Draft KPI tile |
| **PX-145** | Timeline submit de-duplicated (“Save entry”) |
| **PX-276** | Removed PATCH wording from status hints |
| **PX-136** | **Residual** — requires incident linking lane |
| **PX-143** | **Residual** — PDF rendering follow-on (JSON + honest note exist) |

## Test plan
- [x] Vitest targeted helpers (see §5)
- [x] Pytest completion gate + roster assignee (see §5)
- [ ] Staging: assignee pickers, `/capa`, legacy completed investigation banner
