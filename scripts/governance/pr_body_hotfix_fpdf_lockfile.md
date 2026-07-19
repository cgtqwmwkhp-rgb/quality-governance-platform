# Change Ledger (CL-HOTFIX-FPDF-LOCKFILE)

## 1) Summary
- **Feature / Change name:** HOTFIX — pin fpdf2 in requirements.lock + lazy PDF import
- **User goal:** Restore production API boot (login) after DEF-PDF left fpdf import without lock pin
- **In scope:** Regenerate `requirements.lock` to include `fpdf2`; lazy-import FPDF so missing dep cannot crash process import
- **Out of scope:** PDF feature changes; Governance Library waves
- **Root cause:** Dockerfile installs `requirements.lock` preferentially; #1172 added `fpdf2` to `requirements.txt` but lock omitted it → prod `ModuleNotFoundError: fpdf` → 503 (CORS was a browser side-effect)

## 2) Impact Map
- **Backend:** `document_campaign_service.py` lazy import
- **Dependencies:** `requirements.lock` (+fpdf2==2.8.7)
- **Database:** None

## 3) Compatibility & Data Safety
- Additive/lock pin only; PDF export returns 400 if fpdf still missing

## 4) Acceptance Criteria
- [x] AC-01: `requirements.lock` contains fpdf2
- [x] AC-02: Importing `document_campaign_service` does not require fpdf at module import time
- [x] AC-03: Change Ledger complete

## 5–10) Testing / CUJ / Ops / Release / Rollback / Evidence
- Prod verification: `/healthz` 200; login from SWA succeeds
- Rollback: redeploy prior SHA

# Gate Checklist
- [x] Gate 0–1
- [ ] Gate 2 CI
- [ ] Gate 3 staging/prod health
- [x] Gate 4 N/A
- [x] Gate 5 monitoring = healthz
