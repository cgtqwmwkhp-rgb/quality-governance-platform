# Change Ledger — CUJ-P10 Portal Field Work Inbox

## Summary
Adds mobile portal **My Work** inbox at `/portal/work` so SSO field users can see assigned actions (`assigned_to=me`), pending reading, and workforce profile link state — without implementing TrainingTicket matrix, IMMU audit bridge, or ops triage. Depends conceptually on #929 for prod API bake truth; draft can land now.

## Change ledger
- `src/api/routes/engineers.py`: additive `GET /engineers/by-user/me` thin self resolver (404 when unlinked; `portal_work_inbox_viewed` log)
- `frontend/src/api/engineersClient.ts` (+ test): client for by-user/me
- `frontend/src/api/client.ts`: wire `engineersApi`
- `frontend/src/pages/PortalWork.tsx`: portal inbox UI + honest empty/error states + data-testids
- `frontend/src/pages/Portal.tsx`: **My Work** tile between Report and Track
- `frontend/src/App.tsx`: `/portal/work` route under PortalLayout
- `tests/unit/test_engineer_self_inbox.py`: linked + 404 unlinked
- `frontend/src/pages/__tests__/PortalWork.test.tsx`: assigned_to=me + empty/error honesty
- `frontend/tests/e2e/portal-work-inbox.spec.ts`: mocked Playwright CUJ
- `scripts/governance/pr_body_cuj_portal_work_inbox.md`: this ledger

## Impact map
| Surface | Before | After |
|---------|--------|-------|
| Portal home | Report / Track / Help only | + My Work tile → `/portal/work` |
| Field My Work | Admin `/actions` only (different auth store) | Portal inbox with server `assigned_to=me` |
| Engineer self resolve | Only `GET /engineers/{id}` | + `GET /engineers/by-user/me` |
| Unlinked profile | N/A | Honest “Contact supervisor to link profile” |
| Reading ack on mobile | Admin My Reading checkbox theatre | Open document only (no one-tap ack) |

## Compatibility
- Additive API route + FE surfaces only
- No schema/migration changes
- No TrainingTicket / IMMU / ops triage
- No SMTP invention
- Parallel-safe with #929 (env), Complaints, Incident→CAPA; serial after Passport graph entities for competency matrix (out of scope)

## Acceptance criteria
- **AC-01**: Portal home My Work tile navigates to `/portal/work` within 2 taps
- **AC-02**: Inbox calls `GET /actions/?assigned_to=me` and shows honesty label
- **AC-03**: Pending reading section loads `my-pending` with per-slice empty state
- **AC-04**: Linked engineer shows profile card; 404 shows unlinked copy (no fake ticks)
- **AC-05**: Action/reading/passport filter failures toast + inline alert (no silent empty success)

## Testing evidence
- Unit: `tests/unit/test_engineer_self_inbox.py`
- Unit: `frontend/src/pages/__tests__/PortalWork.test.tsx`
- Client: `frontend/src/api/engineersClient.test.ts`
- E2E: `frontend/tests/e2e/portal-work-inbox.spec.ts`

## Critical journeys
- **CUJ-01**: Portal → My Work → assigned action visible (`assigned_to=me`) (CUJ-P10-01)
- **CUJ-02**: Unlinked user → honest passport empty state (CUJ-P10-02)
- **CUJ-03**: Empty actions/reading → per-slice empty copy (not one generic “all caught up”) (CUJ-P10-03)

## Observability
- BE log: `portal_work_inbox_viewed` with `engineer_linked` true/false
- Playwright hooks: `portal-work-btn`, `portal-work`, `portal-work-actions`, `portal-work-reading`, `portal-work-passport-link`, `portal-work-passport-unlinked`, `portal-work-passport-linked`

## Release plan
1. Draft PR now (this change)
2. Land after #929 prod API bake confidence (tip==LIVE)
3. Squash-merge when CI green; do not merge from authoring step alone

## Rollback plan
1. Revert squash commit on main
2. Redeploy prior SHA

## Gate checklist
- [x] Gate 0 — change ledger
- [x] Gate 1 — allowlist only (PortalWork / Portal / App portal routes / engineers thin resolver / clients / tests)
- [ ] Gate 2 — CI green
- [ ] Gate 3 — staging tip
- [ ] Gate 4 — prod tip (requires #929)
- [ ] Gate 5 — evidence pack attached

## Out of scope (explicit)
- TrainingTicket competency matrix / QR passport
- IMMU audit bridge
- Supervisor intake triage
- Portal document acknowledge checkbox
