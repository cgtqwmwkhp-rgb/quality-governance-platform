# ADR-0025: Customer Feedback kinds on one complaints register

**Status**: Accepted
**Date**: 2026-08-24
**Decision Makers**: David Harris (IT / business owner)

## Context

PlantEx records unsolicited customer voice on the existing `complaints` table
and `/api/v1/complaints` API. FB-PR1–PR4 landed a discriminator (`feedback_kind`),
kind-scoped write/portal paths, and a Compliment:Complaint board ratio, behind
`customer_feedback_kinds` default **false** so compliments could not be written
until read-side honesty and the ratio were LIVE.

The remaining product question is whether to rename the table, router, and
`complaint:*` permissions to “feedback”, or keep that identity and turn the
kinds write path on.

## Decision

1. **One register, four kinds.** `complaint | compliment | suggestion | general`
   live on `complaints`. No sibling table. No STI with incidents.
2. **API / table / permissions stay `complaints`.** Routes remain
   `/api/v1/complaints`. Permissions remain `complaint:*`. Labels in the UI say
   Feedback. Tracking codes HMAC the reference; audit rows are immutable; a
   rename would split history.
3. **`customer_feedback_kinds` default on.** Staff and Portal may write
   non-complaint kinds. `CUSTOMER_FEEDBACK_KINDS_ENABLED=false` still subtracts.
4. **Polarity is derived from kind**, never stored. Neutrals (suggestion,
   general) never enter the Compliment:Complaint board ratio.
5. **New prefixes only for new rows:** COMP- | CMND- | SUGG- | FDBK-. Existing
   COMP- refs are never re-minted.

## Consequences

- Production LIVE of this ADR’s implementing PR is what turns kinds-on, not
  merge alone.
- The flag remains a subtract-only kill: false hides the staff kind selector
  and 422s non-complaint writes. It cannot invent a second register.
- Hub remains Safety & Investigations. Child label Feedback. Route `/complaints`
  (optional `/feedback` alias is a later slice).

## Out of scope

- Table/router/permission rename.
- NPS/CSAT, sentiment AI, social ingest, auto-ack email.
- Anonymous portal (PX-312).
- Hub rename. ISO 14001:2026. Voyage embeddings. Entra attestation.

## References

- FB-PR1 #1795 · FB-PR2 #1796 · FB-PR3 #1797 · FB-PR4 #1798 · this PR (FB-PR5)
- `src/domain/services/feedback_kind_policy.py`
- `src/core/config.py` — `customer_feedback_kinds_enabled`
