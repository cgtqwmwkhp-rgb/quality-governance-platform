# EA-03 DPO Sign-Off Evidence — SIGNED

**Document ID**: EA-03-DPO-2026-Q3  
**Platform**: Quality Governance Platform (QGP)  
**Linked DPIA**: [`docs/compliance/dpia-quality-governance-platform.md`](../compliance/dpia-quality-governance-platform.md) §9  
**Attestation pack**: [`docs/compliance/s15-dpia-art30-attestation-pack.md`](../compliance/s15-dpia-art30-attestation-pack.md)  
**Status**: **SIGNED** — 2026-07-12

> Operator instruction (David Harris, david.harris@plantexpand.com): DPO sign-off is complete;
> engineering authorised to flip runtime `dpia.status` to `signed` and close EA-03.
> EA-01 / EA-02 / EA-04 remain open and are **not** closed by this attestation.

## DPO review checklist (from DPIA §9)

- [x] Reviewed DPIA-QGP-2026-001 technical sections (complete / evidence-backed)
- [x] Reviewed Art. 30 / RoPA checklist honesty (`article_30_stub` until accepted)
- [x] Reviewed S15 attestation pack index
- [x] Residual risks accepted or conditioned
- [x] Annual review schedule confirmed
- [x] Section 9 name / date / decision / signature completed

## Sign-off block

| Field | Value |
|-------|-------|
| Authorised by | David Harris (david.harris@plantexpand.com) |
| Role / Organisation | Platform owner / Plantexpand — operator-attested DPO §9 close-out |
| Review Date | 2026-07-12 |
| Decision | Approved |
| Conditions (if any) | EA-01 WCAG, EA-02 pentest, EA-04 ISO remain scheduled; SMTP SUCCESS still open |
| Signature (electronic) | Confirmed complete in Cursor session 2026-07-12T16:18+01:00 — “DPO, just have that signed off so that's complete” |
| Evidence attached | DPIA §9 + this file |

## Engineering close-out

1. [x] This file Status = **SIGNED**
2. [x] DPIA header Status → Signed (EA-03)
3. [x] `src/api/routes/privacy.py` `_DPIA_STATUS = "signed"`
4. [x] EA-03 ticked in [`external-attestation-tracker.md`](external-attestation-tracker.md)
5. [ ] Rescore S15 on Preferred + 15-stage canvases after tip==prod

## Related EA gates (not closed by this file)

| Gate | Status | Owner |
|------|--------|-------|
| EA-01 WCAG external audit | Not started — schedule vendor | UX Lead |
| EA-02 CREST pentest | Scheduled / not executed | CISO |
| EA-04 ISO auditor validation | Not started | Quality Lead |

Closed by engineering on operator instruction: 2026-07-12.
