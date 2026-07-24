# Change Ledger (CL-AUDIT-BUILDER-GENERATE-TIMEOUT)

## Summary
Fix AI Audit Builder false "Generation failed" when Gemini `generate-from-brief` exceeds the default 45s axios write timeout. Raise generate timeout to 300s and show an honest timeout message.

## Change Ledger
| ID | Change |
|---|---|
| AB-TO-01 | `AITemplateGenerator` generate-from-brief uses 300s timeout |
| AB-TO-02 | Distinct timeout error copy (en/cy) |

## Impact Map
- Frontend: AITemplateGenerator generate step only
- Backend: none
- APIs: none
- Database: none

## Compatibility
- Additive timeout override only; other API timeouts unchanged
- Tolerant reader / strict writer applied: Yes
- Breaking changes: None
- Migration plan: N/A
- Rollback strategy (DB): No DB change

## Acceptance Criteria
- AC-01: Generate no longer fails solely because the request exceeds 45s
- AC-02: Timeout errors show generateTimeout copy rather than generic failure
- AC-03: en/cy keys present

## Testing Evidence
- Local code review of axios timeout override path
- CI on this PR

## Critical Journeys
- CUJ-01: Audit Builder → Similar → Generate completes for a normal brief without 45s abort
- CUJ-02: If still slow past 300s, user sees honest timeout guidance

## Observability
- Existing `AITemplateGenerator/generate` error tracking retained

## Release Plan
1. Squash-merge to main
2. SWA prod bake / tip==LIVE
3. Smoke Generate on AI Audit Builder

## Rollback Plan
- Rollback trigger: generate hangs UI unacceptably
- Rollback steps: revert merge commit and redeploy previous tip
- Owner: Platform / Quality

## Evidence Pack
- PR diff + Change Ledger + post-deploy tip==LIVE

## Gate Checklist
- Gate 0: Scope locked (timeout hotfix only)
- Gate 1: FE timeout contract updated
- Gate 2: CI green
- Gate 3: Staging/SWA verification
- Gate 4: tip==LIVE prod
- Gate 5: Smoke CUJ-01
