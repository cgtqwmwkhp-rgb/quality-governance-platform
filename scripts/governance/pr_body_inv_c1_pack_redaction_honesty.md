# Change Ledger (CL-INV-C1-PACK-REDACTION-HONESTY)

> Found while reviewing two real packs for `REF-2026-0012`. Internal `cd23db72` and external
> `0f80b248` are byte-identical: same content SHA-256, same description. The external one carried
> "Personal identities are redacted" on its cover while the Redaction summary further down the same
> page read "No redactions were applied to this pack."
>
> Adjacent, not fixed here: redaction still cannot reach identities written in narrative. That is a
> policy change (DEC-4) and lands with the issue gate in C17. Reports still carry no findings, RCA
> or CAPA (D3) — that is C13. This PR changes what the pack *says*, not what redaction *does*.

## 1) Summary
- **Feature / Change name:** INV-C1 — the customer pack states the redaction it actually performed
- **User goal:** An operator releasing an external pack should be able to trust its cover page. Today the cover asserts that personal identities are redacted regardless of whether anything was, which makes a pack containing identifying narrative look cleared for release.
- **In scope:** Cover-page confidentiality notice on the rendered PDF, derived from the stored `redaction_log`; explicit statement that redaction covers recorded identity fields only.
- **Out of scope:** Changing which fields are redacted; narrative/free-text redaction; a redaction review gate before issue (C17, DEC-4); persisting the issued PDF (C17, DEC-5); pack content (C13); the internal-pack wording, which was already accurate.
- **Feature flag / kill switch:** None — this is report copy on an existing endpoint. Kill SHA = current LIVE `d92c52e62f15`.

## 2) Impact Map (what changed)
- **Frontend:** none.
- **Backend:** `investigation_pack_pdf.py` — `_AUDIENCE_CONFIDENTIALITY` (a static per-audience string) replaced by `confidentiality_notice(audience, redaction_log)` plus `count_field_redactions(redaction_log)`.
- **APIs:** none. Same endpoints, same JSON, same bytes-on-the-wire contract. Only the rendered PDF text differs.
- **Database / flags:** none. No migration.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Pure render-time change. The stored pack payload and its SHA-256 are untouched, so previously issued packs re-render with a truthful cover without invalidating their checksum.
- **Breaking changes:** none.
- **Migration plan:** none.
- **Rollback strategy (DB):** Revert the squash. No data is written by this path.
- **Write-path safety:** The renderer still never reads the live investigation — it only sees the stored pack, so nothing here can widen what a pack discloses. The change can only make the cover claim *less*, never more.

## Compliance Delta
- **PII touched?** No new processing. This reduces the risk of a mis-scoped disclosure by ceasing to assert a control that was not applied.
- **Lawful basis / retention:** unchanged.
- **New processor:** none.
- **UK GDPR Art. 5(1)(a) — transparency:** a pack that asserts redaction it did not perform misrepresents the safeguard applied to that disclosure. This PR removes the misstatement.
- **UK GDPR Art. 5(1)(f) / Art. 32:** the underlying gap — narrative text is never redacted — is now stated on the pack instead of being masked by the assertion, so the releasing operator can apply the control manually until C17 automates the gate.
- **What this PR does not claim:** that narrative identities are now protected; that external packs are safe to release unreviewed; that redaction coverage has changed in any way.

## 4) Acceptance Criteria (AC)
- [x] AC-01: An external pack with an empty redaction log states "No fields were redacted from the sections below." The string "Personal identities are redacted" appears nowhere in the rendered document.
- [x] AC-02: An external pack with redactions reports the count actually applied — "1 field was redacted" / "2 fields were redacted" — matching the entries in the stored log.
- [x] AC-03: `SECTION_OMIT_APPROVED` entries are excluded from that count. An approved section omit is a withholding, not a field redaction, and is already reported separately.
- [x] AC-04: Every external pack states that redaction covers recorded identity fields only, that narrative text is reproduced as written, and that the pack should be reviewed before release — whether or not anything was redacted.
- [x] AC-05: The internal-pack notice is unchanged ("Identities are retained; internal commentary is excluded") and does not gain the narrative caveat.
- [x] AC-06: An unrecognised audience gets no notice rather than a wrong one. A malformed or missing `redaction_log` renders the zero-redaction wording rather than raising.
- [x] AC-07: The notice is latin-1 safe, so it cannot break the Helvetica render.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_pack_pdf.py`: 25 passed (13 new across `TestFieldRedactionCount` and `TestConfidentialityNotice`).
- [x] Regression — `pytest tests/unit -k "investigation or pack"`: 271 passed, 0 failed.
- [x] Types — `mypy src/domain/services/investigation_pack_pdf.py`: clean.
- [x] Rendered-document proof — generated both audiences with `pypdf` text extraction and asserted the cover text, rather than trusting the helper in isolation.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `REF-2026-0012` as it actually happened — identifying detail in the description, nothing matching the identity allow-list. Cover now reads "No fields were redacted from the sections below" and carries the review warning, instead of asserting the identities were redacted.
- [x] CUJ-02: A pack where two identity fields were genuinely redacted reports "2 fields were redacted", and the Redaction summary below it still itemises them by type. Cover and summary now agree.
- [x] CUJ-03: A pack with an approved section omit and no field redactions does not claim a redaction on the strength of the omit.
- [x] CUJ-04: An internal pack is unchanged, so nothing about the internal release path shifts.

## 7) Observability & Ops
- **Logs:** unchanged.
- **Runbook:** Packs already issued re-render with the corrected cover on next download; their stored payload and SHA-256 are unaffected. Until C17 lands, an operator releasing externally must still read the narrative sections themselves — the pack now says so.

## 8) Release Plan
- **Staging:** `/healthz`; generate an external pack on a sandbox investigation with no identity fields; confirm the cover states no fields were redacted and carries the narrative caveat.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip. Re-download `REF-2026-0012` external pack and confirm the corrected cover.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** any external pack rendering a redaction count higher than its stored log, or the internal notice changing.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `d92c52e62f15`. No data migration to unwind.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (no API change; stored payload and checksum untouched; render-time copy only; internal wording held)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — report copy, no flag, no data path)
- [x] **Gate 5:** Production verification plan + monitoring ready
