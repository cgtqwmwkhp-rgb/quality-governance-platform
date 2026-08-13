# Change Ledger (CL-STANDARDS-INT-W8-ATTESTATION)

> **Start gate:** Int-W7 (#1741) LIVE — tip `88c29f5c29be`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Int-W8 — Entra MFA technical attestation (fail-closed).
- **User goal:** ISO 27001 A.8.5 can be covered only when a live Entra read shows MFA enforced; CE stays partial; CEP is never covered by Graph.
- **In scope:** Dedicated Graph reader; conservative CA / security-defaults predicate; read-time injection into TechGapGuard via `attestations=`; hover badges; feature flag default off.
- **Out of scope:** Wiring deploy env vars / Entra app registration; `authenticationStrength` resolution; unique-account / admin-separation attestation; IMS Overview (W9); case auto-map (W10); ExactShare changes; TrapGuard / ingest / `covers_framework`.
- **Feature flag / kill switch:** `ENTRA_ATTESTATION_ENABLED=false` (default). Enabling in production is a separate ops change.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W8-01 | TechGapGuard | `TECHNICAL_ATTESTATION_ENTITY_TYPES` empty; documents cannot cover | Same set stays empty; live kinds arrive on `assess(..., attestations=)` |
| SG-W8-02 | 27001 A.8.5 | Document CEL → `partial` + `tech_gap_attestation_missing` | Attestation PASS lifts the tech-gap downgrade when the cell is otherwise clean |
| SG-W8-03 | CE user_access_control | Stub | MFA PASS → still stub/`partial`; names unattested account-separation elements |
| SG-W8-04 | CEP | Stub | Short-circuit `cyber_essentials_plus_requires_witnessed_test`; Graph cannot cover |
| SG-W8-05 | ExactShare | Warns `tech_gap_attestation_missing` | Unchanged — does not receive the reader result |
| SG-W8-06 | Matrix hover | Tech-gap badge only | Pass/fail MFA badges + as-of timestamp |

## 3) Compatibility & Data Safety
- No schema / migration. No `ComplianceEvidenceLink` writes.
- Default flag off: zero outbound HTTP; technical cells add `"attestation": {"status": "disabled"}` only.
- Dedicated `ENTRA_ATTESTATION_CLIENT_ID` / `_CLIENT_SECRET` — no fallback to the login app.
- `ENTRA_ATTESTATION_QGP_TENANT_IDS` empty ⇒ applies to nobody (no customer-tenant bleed).
- **Rollback strategy:** Set `ENTRA_ATTESTATION_ENABLED=false`, or revert merge and redeploy prior tip `88c29f5c29be`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| A.8.5 closed by a PDF | Blocked (stub) | Still blocked unless live Entra MFA PASS |
| CEP green from Graph | Impossible | Still impossible (hands-on short-circuit) |
| CHAS/SSIP EXACT | Not invented | Still not invented |
| `covers_framework` | Alignment edges only | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag default off → zero HTTP; technical cells `attestation.status=disabled`.
- [x] AC-02: Flag on, creds unset → `unavailable` / `not_configured`; zero HTTP.
- [x] AC-03: QGP tenant not in allowlist → `not_applicable`; zero HTTP.
- [x] AC-04: 27001 A.8.5 + qualifying CA → tech-gap lifted; verdict `covered` when the cell is otherwise clean.
- [x] AC-05: CE user_access_control stays partial on MFA PASS; unattested elements named.
- [x] AC-06: CEP never covered; reason `cyber_essentials_plus_requires_witnessed_test`.
- [x] AC-07: Graph 401/403/429/timeout/non-JSON → `unavailable`; never pass.
- [x] AC-08: Report-only, exclusions, OR+compliantDevice, authenticationStrength → do not qualify.
- [x] AC-09: Matrix batch resolves attestation once; expired cache + Graph error is not a stale PASS.
- [x] AC-10: ExactShare still warns; does not pass `attestations=`.
- [x] AC-11: No Alembic revision.
- [x] AC-12: No token/secret/object id in payload or logs.
- [x] AC-13: TrapGuard / ingest / tech-gap isolation AST tests.
- [x] AC-14: Reader never calls `covers_framework`.
- [x] AC-15: Hover badges + i18n keys in en.json and cy.json.
- [ ] AC-16: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_entra_attestation.py`
- [x] Unit: `tests/unit/test_standards_int_w8_attestation_cells.py`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: A.8.5 cannot be greened by typing `entra_mfa` on a CEL row.
- [x] CUJ-02: CEP cannot be greened by a Graph PASS.

## 7) Observability & Ops
- Config summary logs `entra_attestation_enabled` only (boolean). Never secrets.
- Enabling LIVE later requires: dedicated Entra app with `Policy.Read.All` (application), `ENTRA_ATTESTATION_*` env vars, and `ENTRA_ATTESTATION_QGP_TENANT_IDS` set to Plant Expand's QGP tenant id.
- Health SHA matching the merge commit is **not** sufficient if staging/prod deploy fails.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `88c29f5c29be` (`STACK_MAX=1`).
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.
4. Do **not** wire deploy workflow secrets in this PR. Flag stays off until a governed ops change.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** A technical cell reports `covered` while `attestation.status != pass` in the same response; a `cep` cell reports `tech_gap.covered == true`; Graph 429 storms; matrix p95 +20%.
- **Rollback steps:** `ENTRA_ATTESTATION_ENABLED=false` (no code deploy). Or revert merge; redeploy prior tip `88c29f5c29be` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_int_w8_attestation.md`
- Parent LIVE gate: **PR #1741** (Int-W7) @ `88c29f5c29be`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1741 LIVE confirmed
- [ ] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
