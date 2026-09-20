# Change Ledger (CL-INV-C6-LATE-SOURCE-EVIDENCE)

> Adjacent, not fixed here: the Evidence tab listing both query shapes is C2. Near-miss
> `attachments` JSON URLs still sit outside EvidenceAsset (known leftover). This PR only
> stamps `linked_investigation_id` on uploads that arrive after the investigation opened.

## 1) Summary
- **Feature / Change name:** INV-C6 — adopt evidence added to a source after its investigation opened
- **User goal:** A photo taken on the incident *after* the investigation is opened should appear on that investigation without a second upload.
- **In scope:** On `EvidenceService.upload`, resolve the in-tenant investigation for the source record and set `linked_investigation_id` before commit. Investigation-native uploads are left alone.
- **Out of scope:** Evidence tab query merge (C2); rewriting historical rows that already missed the link; near-miss JSON attachments; bulk Users.
- **Feature flag / kill switch:** None. Kill SHA = LIVE `f65f8ecc2ef8`.

## 2) Impact Map (what changed)
- **Frontend:** none.
- **Backend:** new `evidence_investigation_link.py`; `EvidenceService.upload` sets `linked_investigation_id` when a matching investigation exists in the same tenant.
- **APIs:** none. Same upload endpoint; the stored row now carries the FK that C2 already lists.
- **Database / flags:** none. Uses the existing nullable column.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive write. Uploads with no matching investigation are unchanged.
- **Breaking changes:** none.
- **Migration plan:** none. Historical unlinked assets are not backfilled here.
- **Rollback strategy (DB):** Revert the squash. Rows already linked keep the FK (harmless).
- **Write-path safety:** Missing `tenant_id` refuses to guess (source ids are per-tenant). `source_module=investigation` does not link to itself. Invalid `source_id` does not query.

## Compliance Delta
- **PII touched?** Evidence bytes are already stored; this only copies an investigation id onto the asset row.
- **What this PR does not claim:** that the Evidence tab lists the file (that is C2); that historical late uploads are repaired.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Incident / near miss / RTA / complaint map onto the investigation entity types (`incident` → `reporting_incident`).
- [x] AC-02: Investigation and audit uploads do not invent a link.
- [x] AC-03: A matching in-tenant investigation id is returned and written onto the new asset.
- [x] AC-04: Missing tenant, non-int source id, or unknown module returns None and does not query.
- [x] AC-05: Existing upload validation (type, size, empty file) still fails before any link lookup.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_evidence_investigation_link.py`.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Investigation is already open on incident 12. A photo is uploaded to that incident. The asset is stored with `linked_investigation_id` of that investigation.
- [x] CUJ-02: The same upload with no tenant does not attach another tenant's investigation.
- [x] CUJ-03: A file uploaded on the investigation itself is not re-linked.

## 7) Observability & Ops
- **Logs:** unchanged.

## 8) Release Plan
- **Staging:** Open an investigation from an incident, then upload a new photo on the incident. Confirm `linked_investigation_id` is set (C2 tab will show it once C2 is LIVE).
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** uploads onto the wrong investigation, or investigation-native uploads gaining a different `linked_investigation_id`.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `f65f8ecc2ef8`.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (existing column; fail-closed without tenant)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
