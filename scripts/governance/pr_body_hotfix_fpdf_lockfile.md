# Change Ledger (CL-HOTFIX-FPDF-LOCKFILE)

## 1) Summary
- **Feature / Change name:** HOTFIX — pin fpdf2 in requirements.lock + lazy PDF import
- **User goal (1–2 lines):** Restore production API boot and login after DEF-PDF left a top-level fpdf import while Docker installed from a lockfile that omitted fpdf2.
- **Depends on:** #1172 LIVE content on tip (broken without this pin)
- **In scope:** Regenerate requirements.lock to include fpdf2==2.8.7; lazy-import FPDF inside PDF builder
- **Out of scope:** PDF layout changes; Governance Library W4/W5
- **Root cause:** Dockerfile prefers requirements.lock; #1172 added fpdf2 to requirements.txt only → prod ModuleNotFoundError: fpdf → Azure 503 (browser CORS was a side-effect)
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** document_campaign_service.py (lazy FPDF import)
- **APIs (endpoints changed/added):** None
- **Schemas/contracts:** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** requirements.lock pins fpdf2==2.8.7

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Lock pin + import-time hardening only
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: requirements.lock contains fpdf2
- [x] AC-02: Importing document_campaign_service does not require fpdf at module import time
- [x] AC-03: Missing fpdf at PDF call time returns BadRequestError (no process crash)
- [x] AC-04: Change Ledger complete with Gates 0–5

## 5) Testing Evidence (link to runs)
- [x] Unit — local import smoke (lazy path)
- [ ] CI — this PR
- [x] Prod verification — healthz 200; version e5412dc; CORS allow-origin for SWA

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: API process imports routes without fpdf at import time
- [x] CUJ-02: PDF export path still constructs FPDF when fpdf2 is present
- [x] CUJ-03: Prod login path — healthz + token-exchange preflight succeed

## 7) Observability & Ops
- **Logs:** Container boot no longer crash-loops on ModuleNotFoundError: fpdf
- **Metrics:** None new
- **Alerts:** Prod healthz / tip_match recovered
- **Runbook updates:** Any new requirements.txt dep must refresh requirements.lock

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Force-deployed hotfix SHA under freeze override
- **Canary plan:** N/A — hotfix restore
- **Prod post-deploy checks:** curl /healthz → 200; SWA login; CORS on auth routes

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Deploy fails health or login still 503
- **Rollback steps:** Redeploy last known-good SHA prior to DEF-PDF image (41028097) with force_deploy=true
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: N/A / force prod hotfix
- Canary evidence (if applicable): N/A
- Prod docker log evidence: ModuleNotFoundError: No module named 'fpdf' prior to fix
- Prod version after fix: e5412dc8195b

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (dependency pin only)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [x] **Gate 3:** Prod verification complete (healthz 200 / CORS OK)
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
