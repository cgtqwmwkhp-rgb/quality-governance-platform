# Change Ledger (CL-INV-C14-PACK-BRANDING)

> Adjacent, not fixed here: pack *content* still reprints the source record (C13). Narrative
> redaction is still C17. This PR is chrome only — header, wordmark, footer, page numbers,
> and the default brand colour.

## 1) Summary
- **Feature / Change name:** INV-C14 — Plantexpand branding on investigation customer packs
- **User goal:** Issued PDFs should look like a Plantexpand document (wordmark, footer, page n of m), not a Tailwind-blue band with no page numbers.
- **In scope:** Default brand colour = web `--primary` (78, 118, 10); `PLANTEXPAND` wordmark in the header; footer with organisation + wordmark and `Page {n} of {total}`. No remote `logo_url` fetch; no logo binary added to the repo.
- **Out of scope:** Graphical chronology (C15); ICAM figure (C16); pack section content (C13); C1 honesty copy (held).
- **Feature flag / kill switch:** None. Kill SHA = LIVE `f65f8ecc2ef8`.

## 2) Impact Map (what changed)
- **Frontend:** none.
- **Backend:** `investigation_pack_pdf.py` — FPDF subclass with footer; taller header band; wordmark; default RGB.
- **APIs:** none. Same download endpoint; rendered bytes change.
- **Database / flags:** none. Stored pack payload and SHA-256 are untouched.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Render-time only. Previously issued packs re-render with branding on next download without invalidating their checksum.
- **Breaking changes:** none.
- **Migration plan:** none.
- **Rollback strategy (DB):** Revert the squash. No data written.
- **Write-path safety:** Still renders only the stored pack. Tenant `primary_color` still overrides the default when it is a valid `#rrggbb`.

## Compliance Delta
- **PII touched?** No new processing. C1 cover wording is unchanged.
- **What this PR does not claim:** that the pack now contains findings or RCA; that a raster logo is embedded.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Default brand RGB is `(78, 118, 10)`, not Tailwind `(59, 130, 246)`.
- [x] AC-02: Extracted PDF text contains `PLANTEXPAND`, the organisation name, `Page 1 of`, and the audience label.
- [x] AC-03: An external pack with an empty redaction log still states that no fields were redacted and that narrative is reproduced as written. "Personal identities are redacted" does not appear.
- [x] AC-04: Invalid tenant colour still falls back instead of failing the render.
- [x] AC-05: Missing fpdf2 still fails closed.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_pack_pdf.py` including pypdf text extraction.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: External pack for a named organisation carries the wordmark, footer, and page numbers.
- [x] CUJ-02: C1 honesty notice still prints on that branded page.

## 7) Observability & Ops
- **Logs:** unchanged.

## 8) Release Plan
- **Staging:** Generate internal and external packs; confirm header wordmark and footer page numbers; confirm C1 cover text.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip. Re-download a sandbox pack, not a historically issued customer copy, to review branding.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** missing C1 honesty notice; render failures; remote asset fetches appearing in this path.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `f65f8ecc2ef8`.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (render-only; no remote logo)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
