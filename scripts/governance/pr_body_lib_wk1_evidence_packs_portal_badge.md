# Change Ledger (CL-LIB-WK1-EVIDENCE-PACKS-PORTAL-BADGE)

> Base: `origin/main` @ `e8fbfe438` (WI-1 #1687 merged). Fixtures + portal badge
> only — no alembic; CEL adapter deferred.

## 1) Summary

- **Feature / Change name:** Library WK-1 — Framework evidence packs + portal
  CURRENT coverage badge (L-47 / L-48)
- **User goal (1–2 lines):** Auditors get fixture-matched ISO 9001 / UVDB B2 /
  Planet Mark packs from typed CEL-shaped rows; employees on portal reading see
  an honest CURRENT (or superseded) coverage badge at 360px — no editor.
- **In scope:**
  - NEW pure builder `framework_evidence_pack_builder.py` (dict rows → pack)
  - Frozen fixtures under `specs/governance-library/fixtures/evidence-packs/`
  - Portal `PortalCoverageBadge` + helpers wired into `PortalReading`
  - Isolated unit/vitest coverage; this Change Ledger
- **Out of scope / deferred:**
  - CEL ORM / `compliance.py` / `governed_knowledge` pack route adapter
  - Alembic; standards/clauses; cover_kind writers
  - Coverage % formula by `cover_kind`; twin `document_coverage_claims` tables
- **Feature flag / kill switch:** None — builder + UI scaffold; no new flag

## 2) Impact Map (what changed)

- **Frontend:** `PortalCoverageBadge` + `portalCoverageBadgeHelpers.ts`; `PortalReading`
  shows badge; optional `document_issue_state` on assignment type; i18n en/cy
- **Backend:** NEW `src/domain/services/framework_evidence_pack_builder.py` only
  — **no** edits to `compliance.py` / CEL models / governed_knowledge
- **APIs:** None in this slice (adapter deferred)
- **Database:** None (no alembic)
- **Tests:** `tests/unit/test_lib_wk1_framework_evidence_packs.py`;
  `PortalCoverageBadge.test.tsx`
- **Docs/fixtures:** `specs/governance-library/fixtures/evidence-packs/*`

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UI; builder is unused until CEL adapter
- **Breaking changes:** None
- **Migration plan:** N/A this slice
- **Rollback strategy:** Revert commit / drop badge import

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Framework evidence packs | Campaign / GKB audit packs only; no Library L-47 fixtures | Fixture-backed ISO 9001 / UVDB B2 / Planet Mark packs from typed rows |
| CEL / scheme SoT | WI-1 merged (#1687) owns harden | WK-1 does **not** touch CEL/standards/clauses/alembic/compliance routes |
| Coverage twin tables | Forbidden (F-3 / D15) | Still forbidden; builder sets `no_coverage_twin_tables` |
| Portal CURRENT honesty | Assignment status only | CURRENT / Superseded / Draft badge scaffold on PortalReading (360px) |
| Editor on portal | Must not appear (L-48) | Badge only — no editor chrome |

## 4) Acceptance Criteria (AC)

- [x] AC-01 (L-47): Builder emits packs for `iso9001` / `uvdb_b2` / `planet_mark`
  matching frozen fixtures (signal honesty; NC excluded by default)
- [x] AC-02 (L-47): Fixtures carry WI-1-shaped fields (`cover_kind`,
  `confirmed_by_id`, `catalogue_key`) without importing WI-1 conflict modules
- [x] AC-03 (L-48): PortalReading shows coverage badge; CURRENT + version truncate
  safely in max-w-lg / 360px row; no editor
- [x] AC-04: Unit + vitest green for packs + badge helpers
- [ ] AC-05: Wire CEL → typed-row adapter + export route — **deferred** (follow-on)
- [ ] AC-06: Assignment API projects `document_issue_state` — **deferred**
  (badge already tolerant when absent)

## 5) Testing Evidence

- [x] `pytest tests/unit/test_lib_wk1_framework_evidence_packs.py -q`
- [x] Vitest `PortalCoverageBadge.test.tsx`
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Fixture rows → ISO 9001 pack excludes NC + cross-scheme noise
- [x] CUJ-02: Portal reading card with `document_issue_state=CURRENT` shows badge
- [ ] CUJ-03: Live CEL export pack download — deferred to adapter follow-on

## 7) Observability & Ops

- **Playwright hooks:** `portal-coverage-badge`, `portal-coverage-badge-version`
- **Logs / Metrics:** None new

## 8) Release Plan

1. Open PR on tip rebased onto WI-1 merge (`e8fbfe438`)
2. Merge only after CI green (no alembic — safe vs WI-2)
3. Tip-chase STG/PROD before conveyor PROD/DONE
4. Follow-on: CEL adapter after WI-1 PROD LIVE if still needed

## 9) Rollback Plan

- **Trigger:** Badge confuses employees; pack fixture drift
- **Steps:** Revert merge; redeploy prior tip (no schema in this slice)
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)

- Branch: `feat/lib-wk1-evidence-packs-portal-badge`
- Base: `e8fbfe438` (WI-1 #1687)
- Depends: WI-1 merged to main (adapter still deferred)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — fixtures + badge; no WI-1 path edits
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] No `compliance_evidence.py` / `standard.py` / clauses edits
- [x] No alembic revision
- [x] No `compliance.py` / `governed_knowledge*` edits
- [x] PortalReading + NEW builder/fixtures/tests only (+ additive assignment type / i18n)
- [x] Zero path overlap with WI-2 file-homes prep
