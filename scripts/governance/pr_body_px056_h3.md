# Change Ledger (CL-PX-056-H3)

## Scope
- Add `engineer_ids` to document-campaign audiences and resolve them to linked, active tenant-scoped QGP user IDs before campaign persistence.
- Return HTTP 422 with `unlinked_engineer_ids` when any selected roster employee cannot be resolved.
- Add a roster-based “Selected workforce employees” campaign audience picker with explicit linked/unlinked status.
- Add Python and Vitest coverage.

## Controls
- [x] Engineer IDs are tenant scoped and resolved only through active linked users.
- [x] Missing, unlinked, out-of-tenant, or inactive linked users are returned together in `unlinked_engineer_ids`.
- [x] Campaign persistence retains resolved user IDs; it does not store or trust engineer IDs for delivery.
- [x] Existing document-update authorization remains unchanged.

## Verification
- [x] `pytest -q tests/unit/test_document_campaign_service.py`
- [x] `npx vitest run src/pages/__tests__/documentCampaignHelpers.test.ts`
- [x] `npx tsc --noEmit`
