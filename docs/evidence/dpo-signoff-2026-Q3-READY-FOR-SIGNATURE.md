# EA-03 DPO Sign-Off Evidence — READY FOR SIGNATURE

**Document ID**: EA-03-DPO-2026-Q3  
**Platform**: Quality Governance Platform (QGP)  
**Linked DPIA**: [`docs/compliance/dpia-quality-governance-platform.md`](../compliance/dpia-quality-governance-platform.md) §9  
**Attestation pack**: [`docs/compliance/s15-dpia-art30-attestation-pack.md`](../compliance/s15-dpia-art30-attestation-pack.md)  
**Status**: **UNSIGNED — awaiting DPO** (engineering must not invent a signature)

> This file is the EA-03 evidence artifact required by the Preferred S15 human unlock plan.
> Fill the signature block below. Until then, runtime `dpia.status` must remain `pending_dpo_signoff`.

## DPO review checklist (from DPIA §9)

- [ ] Reviewed DPIA-QGP-2026-001 technical sections (complete / evidence-backed)
- [ ] Reviewed Art. 30 / RoPA checklist honesty (`article_30_stub` until accepted)
- [ ] Reviewed S15 attestation pack index
- [ ] Residual risks accepted or conditioned
- [ ] Annual review schedule confirmed
- [ ] Section 9 name / date / decision / signature completed **by DPO** (not engineering)

## Sign-off block (DPO only)

| Field | Value |
|-------|-------|
| DPO Name | _[To be completed by DPO]_ |
| Role / Organisation | _[To be completed by DPO]_ |
| Review Date | _[YYYY-MM-DD]_ |
| Decision | Approved / Approved with conditions / Rejected |
| Conditions (if any) | _[To be completed by DPO]_ |
| Signature (wet or electronic) | _[DPO signature]_ |
| Evidence attached | DPIA §9 + this file |

## Engineering close-out (only after signature exists)

1. Confirm this file’s Status line reads **SIGNED** with real name/date/signature above.
2. Update DPIA header Status from “Pending DPO Sign-Off” → signed.
3. Update `src/api/routes/privacy.py` `dpia.status` from `pending_dpo_signoff` → signed value.
4. Tick EA-03 in [`external-attestation-tracker.md`](external-attestation-tracker.md).
5. Rescore S15 on Preferred + 15-stage canvases.

## Related EA gates (not closed by this file)

| Gate | Status | Owner |
|------|--------|-------|
| EA-01 WCAG external audit | Not started — schedule vendor | UX Lead |
| EA-02 CREST pentest | Scheduled / not executed | CISO |
| EA-04 ISO auditor validation | Not started | Quality Lead |

Prepared by engineering for DPO action: 2026-07-12 (human unlock plan Track D).
