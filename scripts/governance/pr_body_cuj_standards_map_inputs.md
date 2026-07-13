# Change Ledger (CL-CUJ-STANDARDS-MAP-INPUTS)

## File allowlist (exclusive)
- `src/api/routes/governed_knowledge.py` (signal_type filter + reject rationale soft-compat)
- `frontend/src/api/knowledgeBankClient.ts`
- `frontend/src/api/knowledgeBankClient.test.ts`
- `frontend/src/pages/KnowledgeExceptions.tsx`
- `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx`
- `frontend/src/components/StandardsAssessmentPanel.tsx`
- `frontend/src/components/__tests__/StandardsAssessmentPanel.test.tsx` (NEW)
- `tests/unit/test_exceptions_signal_type_filter.py` (NEW)
- `scripts/governance/pr_body_cuj_standards_map_inputs.md`

**Zero overlap** with documents-search (`Documents.tsx`) and document-version-control (`DocumentDetail` / `documents.py` / DocumentControl). Avoid Workforce TrainingTicket (#936), IMMU audit_service rewrite, portal work, ops triage. Soft-compat reject body so DocumentDetail legacy callers still work.

## 1) Summary
- **Feature / Change name:** CUJ — Harden map documents/cases → standards (Assessor/GKB)
- **User goal:** Clear Map CTA on cases; Exceptions inbox uses server `signal_type` filter with honest page-cap copy; rejects carry rationale when provided.
- **In scope:** `signal_type` query on `/exceptions`; FE wiring; StandardsAssessmentPanel CTA; reject rationale prompts; tests
- **Out of scope:** DocumentDetail evidence tab rewrite (version-control lane); Workforce competence_gap loop; WL2 watch→Actions beyond shared client
- **Stack:** `main` tip including #926/#928/#929/#932

## 2) Impact Map
- **Backend:** `list_exception_inbox` `signal_type`; reject accepts optional rationale body
- **Frontend:** Exceptions + StandardsAssessmentPanel + knowledgeBankClient
- **DB/migrations:** None

## 3) Compatibility & Data Safety
- Additive query param; reject body optional (legacy clients marked honestly in notes)
- Breaking: None for existing callers omitting body

## 4) Acceptance Criteria
- [x] AC-01: GET `/exceptions?signal_type=` filters server-side
- [x] AC-02: KnowledgeExceptions passes signalType; honesty copy says server filters ≤200
- [x] AC-03: StandardsAssessmentPanel CTA = “Map to ISO / UVDB / Planet Mark”
- [x] AC-04: Reject from panel/Exceptions requires rationale (≥3 chars)
- [x] AC-05: Unit tests for client + panel + enum/request

## 5–6) Testing / CUJ
- [x] knowledgeBankClient signal_type + reject body
- [x] StandardsAssessmentPanel CTA + rationale gate
- [x] KnowledgeExceptions map banner + honesty
- [x] Backend request/enum unit

## 7–10) Ops / Release / Rollback / Evidence
- Draft only; conveyor merge; revert on regress; Gate 0/1 complete

---

# Gate Checklist
- [x] Gate 0 — Change Ledger
- [x] Gate 1 — Exclusive allowlist
- [ ] Gate 2 — CI green
- [ ] Gate 3–5 — staging/prod evidence

## Test plan
- [x] vitest knowledgeBankClient + StandardsAssessmentPanel + KnowledgeExceptions
- [x] pytest test_exceptions_signal_type_filter.py
- Do **not** merge until conveyor review
