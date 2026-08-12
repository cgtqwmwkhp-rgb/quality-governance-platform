# Change Ledger (CL-STANDARDS-WAVE2-PR-D)

## 1) Summary
- **Feature / Change name:** Standards Wave 2 PR-D slice 1 — EXACT shared-apply + undo.
- **User goal:** From an Evidence Workspace cell, share one conformance evidence link onto EXACT peer columns from PEL-HSEQ-5064, with a create-only write and scoped soft-delete undo.
- **In scope:** CEL create-if-absent writer; `ExactShareService` plan/apply/undo; cell-aggregate `exact_share` preflight; POST apply/undo; ExactShareBanner.
- **Out of scope:** Schedule deep-links, cert countdown, SLA/owner columns, export appendix, NEAR share, Wave 3.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-D-01 | CEL writer | Upsert only (rewrites title/notes/confirmer) | `create_evidence_links_if_absent` create-only sibling |
| SG-D-02 | Cell aggregate GET | No share preflight | `exact_share` plan block (EXACT peers only) |
| SG-D-03 | Evidence write API | Manual link per clause | `POST /evidence/exact-share` + `/undo` |
| SG-D-04 | Evidence workspace | No share UX | `ExactShareBanner` above tabs |

- **Frontend:** types, client methods, hook `refetch`, ExactShareBanner, EvidenceWorkspaceHost.
- **Backend:** writer, `standards_exact_share_service`, compliance routes; TrapGuard `version_id`.
- **Database:** No Alembic.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API fields/paths; create-only writes never rewrite existing CEL rows.
- **Tolerant reader / strict writer applied?** Yes — request models `extra="forbid"`; undo skips modified/foreign ids.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — soft-deleted links remain tombstoned; revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Cross-framework evidence share | Manual per-clause links; risk of upsert confirmer rewrite | EXACT-only create; D15 confirmer preserved on existing rows |
| Cover gate honesty | Operator could share onto blocked cells | Source + target `cover_blocked` (NC or action) refuse apply |
| Trap / DIFFERENT / UNIQUE | Could be confused with row verdict | Targets from pair `peers` with verdict EXACT only |
| Undo SoR | N/A | Soft-delete created ids only; skip if `updated_at > applied_at` |

## 4) Acceptance Criteria (AC)
- [x] AC-01: DIFFERENT/UNIQUE peers never offered as EXACT share targets.
- [x] AC-02: NEAR peers not offered (addition not attested).
- [x] AC-03: Row DIFFERENT still offers genuine EXACT pair (e.g. 9.1.2 14001↔45001).
- [x] AC-04: Unloaded matrix / source cover-blocked / open NC or action targets named ineligible.
- [x] AC-05: Create-only writer leaves existing title/notes/confirmer untouched; IntegrityError → existing.
- [ ] AC-06: Hosted CI green; STG=PROD tip LIVE after merge.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `test_standards_exact_share_service`, `test_compliance_evidence_link_create_only`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens EXACT cell with conformance evidence → banner lists eligible peers; blocked peers show reason.
- [x] CUJ-02: Apply creates peer CEL rows; Undo soft-deletes those ids when unmodified.

## 7) Observability & Ops
- No new telemetry. Conflict responses use `EXACT_SHARE_*` codes with structured `details`.
- Support: if share is refused after matrix re-import, refresh workspace (matrix_version_id mismatch).

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (STACK_MAX tip-chase; allowlist after #1732 LIVE).
2. Staging: open `/compliance` matrix → EXACT cell workspace → share → undo.
3. Promote PROD; verify `/api/v1/health` version = main tip.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Share creates links on DIFFERENT peers, overwrites existing CEL metadata, or undo deletes unmodified foreign links.
- **Rollback steps:** Revert merge commit; redeploy prior tip via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/standards-wave2-pr-d-ops`
- Ledger: `scripts/governance/pr_body_standards_wave2_pr_d.md`
- Parent LIVE: #1732 @ `c4554169`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Hero board / mission / allowlist updated after LIVE
