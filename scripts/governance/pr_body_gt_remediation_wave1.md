# Change Ledger (CL-GT-REMEDIATION-WAVE1)

## File allowlist (exclusive)

- `alembic/versions/20260718_capa_nm_rta.py`
- `alembic/versions/20260719_rls_gt_exp.py`
- `alembic/versions/20260719_case_risk_jn.py`
- `frontend/src/App.tsx`
- `frontend/src/api/engineersClient.ts`
- `frontend/src/components/investigations/handoffLinks.ts`
- `frontend/src/components/investigations/handoffLinks.test.ts`
- `frontend/src/components/realtime/NotificationCenter.tsx`
- `frontend/src/hooks/useServiceWorker.ts`
- `frontend/src/pages/NearMissDetail.tsx`
- `frontend/src/pages/PortalWork.tsx`
- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/__tests__/PortalWork.test.tsx`
- `frontend/tests/e2e/portal-work-inbox.spec.ts`
- `src/api/routes/_action_unified.py`
- `src/api/routes/actions.py`
- `src/api/routes/capa.py`
- `src/api/routes/engineers.py`
- `src/api/routes/health.py`
- `src/api/routes/incidents.py`
- `src/api/routes/investigations.py`
- `src/api/routes/near_miss.py`
- `src/api/routes/ocr_ops.py`
- `src/api/routes/privacy.py`
- `src/api/routes/risk_register.py`
- `src/api/schemas/engineer.py`
- `src/domain/models/__init__.py`
- `src/domain/models/capa.py`
- `src/domain/models/risk_register.py`
- `src/domain/services/audit_service.py`
- `src/domain/services/capa_service.py`
- `src/domain/services/case_risk_links.py`
- `src/domain/services/compliance_automation_service.py`
- `src/domain/services/incident_risk_links.py`
- `src/domain/services/investigation_closure_helpers.py`
- `src/domain/services/investigation_service.py`
- `src/domain/services/near_miss_risk_links.py`
- `src/domain/services/risk_scoring.py`
- `src/domain/services/risk_service.py`
- `src/domain/services/workflow_engine.py`
- `src/infrastructure/middleware/tenant_context.py`
- `src/infrastructure/upstream/ai_status.py`
- `src/main.py`
- `tests/e2e/test_compliance_automation.py`
- `tests/fixtures/ocr/capabilities.json`
- `tests/unit/test_actions_my_work_filters.py`
- `tests/unit/test_audit_capa_closure_bridge.py`
- `tests/unit/test_capa_service.py`
- `tests/unit/test_case_risk_links.py`
- `tests/unit/test_engineer_self_inbox.py`
- `tests/unit/test_ocr_artifacts.py`
- `tests/unit/test_rls_force_expand_actions.py`
- `tests/unit/test_rls_force_expand_docs.py`
- `tests/unit/test_rls_gt_exp.py`
- `tests/unit/test_tenant_context_middleware.py`
- `tests/unit/test_workflow_engine.py`
- `tests/unit/test_investigation_closure_gate.py`
- `tests/unit/test_risk_service.py`
- `scripts/governance/pr_body_gt_remediation_wave1.md`

**Zero overlap** with E4 Azure DI prod key enablement, partner token surface, or SWA workflow YAML.

## 1) Summary

- **Feature / Change name:** fix(gt) — Golden-Thread UAT remediation wave 1 (D01–D21)
- **User goal:** Clear intensive UAT fails/flags (S1–S4) so case lifecycle intake→work→CAPA/risk→evidence→close is fail-closed, tenant-safe, and operationally honest
- **In scope:** OCR dispute auth; risk scoring on risks_v2; investigation close CAPA/template gates; case↔risk junction dual-write; RLS expand; near-miss CAPA; action spine capa_items; CAPA verification close; slash dual-mount; health version; FE route aliases; notify paths; tenant-filtered sources; escalations honesty; readyz contracts; privacy AI honesty; heat-map bands; portal engineer link 200; RIDDOR stubbed status
- **Out of scope:** Dropping legacy linked_risk_ids CSV/JSONB; full OpenAPI baseline regen (D22 follow-up); enabling Azure DI dual-OCR in prod
- **Root cause (research):** Golden-thread UAT 100-round CONDITIONAL GO packed 22 defects across auth, dual risk stores, soft FK links, RLS gaps, close gates, FE dead ends, and honesty stubs

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| OCR dispute/ack | Public write | Auth + actor required |
| Risk scoring | Legacy `risks` | Prefers `risks_v2` / EnterpriseRisk |
| Investigation close | CAPA/items ignored | CAPAAction + CAPAItem + template codes gated |
| Case↔risk | CSV/JSONB only | `case_risk_links` junction + dual-write |
| Tenant RLS | evidence_assets / risks_v2 missing | FORCE RLS + middleware catalog |
| Near-miss CAPA | Investigation-gated | CAPASource.NEAR_MISS / RTA first-class |
| My Work | capa_items invisible | Projected as `capa_item:{id}` |
| Finding close | Desync advisory | Fail-closed if CAPAs open |
| CAPA CLOSED | No verification evidence | Requires verification_result/comment |
| Staff FE routes | /capa /my-work /evidence 404 | Redirect aliases |
| Portal engineer me | Network 404 | `200 { linked: false }` |
| Heat map | Zero bands vs list | Aligned 12–16 high + client fallback |
| RIDDOR / escalations | Looked live | Honest stubbed / empty |

## 3) Compatibility & Data Safety

- Migrations: `20260718_capa_nm_rta` → `20260719_rls_gt_exp` → `20260719_case_risk_jn` (≤32 char revision ids)
- Junction dual-write; CSV/JSONB retained for rollback compatibility
- evidence_assets NOT NULL applied only when parent backfill clears nulls
- Slash aliases retain both `""` and `"/"` mounts
- Rollback: revert merge; downgrade junction then RLS expand; enum ADD VALUE irreversible (safe no-op downgrade)

## 4) Acceptance Criteria

- [x] AC-01: OCR dispute/ack require CurrentUser (D01)
- [x] AC-02: Risk scoring prefers EnterpriseRisk / risks_v2 (D02)
- [x] AC-03: Investigation close gates CAPA + capa_items + template codes (D03/D04)
- [x] AC-04: case_risk_links junction + dual-write + junction-first read (D05)
- [x] AC-05: evidence_assets + risks_v2 in RLS_TABLES + FORCE RLS migration (D06)
- [x] AC-06: Near-miss/RTA CAPA source + FE gate removed (D07)
- [x] AC-07: capa_items projected into unified /actions (D08)
- [x] AC-08: Finding close fail-closed when CAPAs open (D09)
- [x] AC-09: CAPA CLOSED requires verification evidence (D10)
- [x] AC-10: Slash dual-mount + health BUILD_SHA + FE redirects (D11–D13)
- [x] AC-11: Notify/push paths + tenant-filtered get_source_record (D14/D15)
- [x] AC-12: Escalations empty; readyz contracts; privacy AI honesty; heat-map; portal linked=false; RIDDOR stubbed (D16–D21)
- [ ] AC-13: tip==LIVE; migrations applied; prod smoke green; UAT retest rounds pass

## 5) Testing Evidence

- Unit: OCR auth, CAPA close, capa_items filters, finding close bridge, case_risk_links, RLS gt exp, engineer self-inbox, workflow escalations
- FE: PortalWork linked=false; NearMiss handoff; RiskRegister bands
- [ ] Post-merge: three retest rounds + 74-round board until PASS

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Intake → raise risk → junction + scoring on risks_v2
- [x] CUJ-02: Investigation/finding close blocked while CAPA open; CAPA close needs verification
- [x] CUJ-03: Near-miss creates CAPA without investigation gate; My Work shows capa_item keys

## 7) Observability

- OCR capabilities advertise `dispute_ack_auth_required`
- /readyz contract tags (`flat_v1` / `nested_v1`)
- RIDDOR `status=stubbed` + `gateway: not_connected`

## 8) Release Plan

- Squash-merge tip==LIVE → migrate three revisions → SWA bake → prod smoke → UAT retest rounds 1–3 + 74 board

## 9) Rollback Plan

- **Rollback steps:** Revert squash on main; downgrade `20260719_case_risk_jn` then `20260719_rls_gt_exp` when safe; leave capa enum values
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- This Change Ledger
- Golden-thread UAT canvas D01–D22
- Prior tip: `ebd1dbac` (#1021)

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — touched surfaces
- [x] **Gate 2:** Unit — remediation suites green locally
- [x] **Gate 3:** Frontend — redirects, portal, heat-map, near-miss
- [ ] **Gate 4:** tip==LIVE prod verification + UAT retest PASS
