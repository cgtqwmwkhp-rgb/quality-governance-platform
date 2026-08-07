# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Compliance Schedule — AI Regulatory basis assist (Track C)
- **User goal (1–2 lines):** On Add/Edit obligation, suggest a regulatory basis from
  the Standards catalogue and a curated UK H&S map (optionally re-ranked by AI),
  then Accept to fill free text and persist a structured Standards link.
- **In scope:** Suggest/clarify endpoints; deterministic UK map + DB Standards matching;
  propose→confirm UI on `RequirementFormDialog`; nullable
  `regulatory_standard_id` / `regulatory_clause_id` FKs; client feature flag.
- **Out of scope:** Doc Graph tables; multi-clause join table (v2); enabling the flag
  in any environment; catalogue template backfill of Standards links.
- **Feature flag / kill switch:** `COMPLIANCE_SCHEDULE_REGULATORY_AI_ENABLED` /
  FE `compliance_schedule_regulatory_ai`, **default off**. Also requires CS module
  open (`COMPLIANCE_SCHEDULE_ENABLED` / `compliance_schedule`) and borrows the CS
  kill switch. Confidence threshold:
  `COMPLIANCE_SCHEDULE_REGULATORY_AI_CONFIDENCE_THRESHOLD` (default 0.7).

## 2) Impact Map (what changed)
- **Frontend:** `RequirementFormDialog`, `RegulatoryBasisAssist`, assist state
  machine + i18n copy, `complianceScheduleClient`, `useFeatureFlag` default.
- **Backend:** `compliance_schedule_regulatory_ai_service`, UK map data,
  CS routes `/regulatory-basis/suggest` + `/clarify`, schemas, create/update
  validation for Standards FKs, `ClientFeature` catalogue entry, settings.
- **APIs:** Additive POST endpoints under `/api/v1/compliance-schedule/…`.
  Requirement create/update/response gain optional regulatory FK fields.
- **Database:** Alembic `20261013_cs_reg_link` — nullable FKs on
  `compliance_requirements` (no RLS change; tenant_isolation unchanged).
- **Config/env/flags:** Two new settings, both default closed / 0.7.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive + Flagged.
- **Tolerant reader / strict writer applied?** Yes. Existing clients omit the new
  FK fields; Accept is the only path that sets them from AI. Hand-editing the
  basis text clears the FKs so citation and link cannot silently disagree.
- **Breaking changes:** None.
- **Migration plan:** Additive nullable columns; no backfill.
- **Rollback strategy (DB):** Downgrade drops the two FKs/indexes/columns. Free-text
  `regulatory_basis` is unchanged.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Suggest button appears only when CS + regulatory AI flags are on.
- [x] **AC-02:** Suggest returns ranked candidates
  `{label, regulation_or_standard_code, standard_id?, clause_ids?, confidence,
  rationale, source}`; top confidence &lt; threshold yields 2–4 clarifying questions.
- [x] **AC-03:** Clarify answers re-suggest; Accept fills `regulatory_basis` and
  stores `regulatory_standard_id` / primary `regulatory_clause_id` for create/update.
- [x] **AC-04:** Never auto-applies without Accept (machine property + UI tests).
- [x] **AC-05:** AI unconfigured / unavailable fails soft with a clear notice and
  still returns deterministic catalogue/UK-map matches.
- [x] **AC-06:** AI cannot mint `standard_id` / `clause_ids`; invented codes are
  capped below the clarification threshold.
- [x] **AC-07:** FRA-style title → Fire Safety Order (FSO2005) candidate without AI.
- [x] **AC-08:** Flag off / module closed → 404 (no disclosure).

## 5) Testing Evidence (link to runs)
- [x] Unit — `test_uk_regulatory_basis_map.py`,
  `test_compliance_schedule_regulatory_ai_service.py`,
  `test_compliance_schedule_regulatory_link_validation.py`,
  `test_client_feature_catalogue.py` (34 passed).
- [x] Vitest — assist machine, `RegulatoryBasisAssist`,
  `RequirementFormDialog` accept/hand-edit (29 passed).
- [ ] Integration / OpenAPI / E2E — deferred to CI (flag-off in every env).

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Add obligation → Suggest → Accept FSO candidate → create payload
  includes basis text + `regulatory_standard_id`.
- [x] **CUJ-02:** Accept then hand-edit basis → create payload clears FKs.
- [x] **CUJ-03:** Low confidence → clarifying questions → re-suggest via `/clarify`.

## 7) Observability & Ops
- **Logs:** Fail-soft AI ranking logs at ERROR with stack; AiDecisionLog row when
  the model is actually invoked (`auto_applied=False` always).
- **Alerts/dashboard:** None new.
- **Runbook / rollback:** Flip
  `COMPLIANCE_SCHEDULE_REGULATORY_AI_ENABLED=false` (or close CS). Revert migration
  only if the columns must be removed.

## 8) Release Plan
- **Staging:** Deploy with flags off; optional enable on one tenant for UAT.
- **Production:** Same — flag remains off until an explicit enablement change.
- **Migration timing:** Runs with normal Alembic upgrade (additive).

## 9) Evidence & Links
- Branch: `feat/cs-regulatory-basis-ai`
- Worktree: `/tmp/qgp-wt-cs-reg-ai`

## 10) Gate Checklist
- [x] Change Ledger complete
- [x] Flags default off
- [x] No Doc Graph tables touched
- [x] Tests not weakened
- [x] Propose→confirm only

---

# Compliance Delta

| Control | Impact | Notes |
|---------|--------|-------|
| AI assist / human-in-the-loop | Additive | Suggestions never auto-apply; Accept required |
| Standards linkage | Additive | Nullable FKs; free-text citation retained |
| Feature disclosure | Unchanged | 404 when flag/module closed |
| Tenancy | Hardened | Cross-tenant Standards refused on write; suggest query filters tenant |
