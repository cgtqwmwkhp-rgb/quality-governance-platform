# ADR-0026: Competence is issued, demonstrated and statutory — three facts, three owners

**Status**: Accepted
**Date**: 2026-09-02
**Decision Makers**: David Harris (IT / business owner)

## Context

PlantEx already holds engineer competence in two systems of record that QGP does
not own. PAMS decides which plant characteristics a technician is **issued**
against, and IT-Admin is who changes PAMS. Citation holds the **statutory**
training that reaches QGP as the Atlas training matrix import, and the HR
Advisor is who changes Citation.

CB-PR1–PR5 landed the read side of that behind `competence_board_enabled`
default **false**: an hourly PAMS snapshot and a board (CB-PR1), plant and
statutory change requests to the owning mailbox (CB-PR2), the Atlas family and
the person union (CB-PR3), an assessment overlay bound to a PAMS characteristic
(CB-PR4), and location coverage quorum n-of-m (CB-PR5). Nothing on that path
writes PAMS or Citation, and nothing creates a QGP User.

The remaining question is not another endpoint. It is whether one plant cell may
be treated as a single "competent" boolean that QGP is allowed to set. It may
not, and the flag cannot be turned on until that is written down: an assessment
signed off in QGP is evidence that competence was *demonstrated*, and it is not
an issuance. Conflating the two would let a QGP sign-off read as authorisation
to operate plant, which only PAMS can grant.

## Decision

1. **Issued is PAMS's fact.** QGP snapshots `vw_plantex_engineercompetence` and
   renders it. QGP never issues an INSERT, UPDATE or DELETE against a PAMS
   competence row, and the board carries no mark-competent control. A revoke or
   issue is requested by a change request to the IT-Admin mailbox, and that
   request auto-closes only when a later snapshot already matches what was
   asked for. Being issued is not a claim that the holder is currently
   authorised; it is the claim that PAMS says so.
2. **Demonstrated is QGP's fact.** It is an overlay on an already-issued plant
   cell, produced by a completed assessment explicitly bound to that
   characteristic (CB-PR4). A pass writes nothing to PAMS. A fail or conditional
   outcome does not delete or suspend issuance either — it opens a plant revoke
   request for IT-Admin to action in PAMS. Until a bound assessment has
   completed, the cell carries no `demonstrated` value at all: an absent overlay
   is honest, and a grey "not assessed" badge would invent a judgement nobody
   made.
3. **Statutory is Citation's fact.** It reaches QGP only through the Atlas
   training matrix import. QGP never writes Citation, and a statutory change
   request goes to the HR Advisor mailbox. An Atlas person who maps to no
   engineer is still shown; no User is created to hold them.
4. **Coverage is a location duty.** A quorum is n-of-m cover held at a place
   (CB-PR5) and it sits on the location obligation as a second fact. It is not a
   per-person compliance-schedule row: ADR-0020 stands, the requirement holds
   the schedule and records are occurrences. Named appointed people stay on the
   Atlas board where their certificates live.
5. **`competence_board_enabled` default on.** `COMPETENCE_BOARD_ENABLED=false`
   / `FF_COMPETENCE_BOARD=false` remains a subtract-only kill: the board,
   coverage, coverage-quotas, assessment-binds and change-requests endpoints
   return 404, and the compliance schedule emits no coverage fields and issues
   no extra query. The flag can only open and close read paths that already
   exist. It cannot invent a PAMS write path, because none is implemented.
6. **The live CompetencyDashboard is not replaced by this slice.** Flag-on here
   means the API is reachable, plus any nav already keyed off this flag. The WDP
   analytics page keeps its own surface, and no new board UI is introduced.

## Consequences

- Production LIVE of this PR is what turns the board on, not merge alone. The
  deploy workflows never write `COMPETENCE_BOARD_ENABLED`, so the code default
  is what applies — unless an operator has set the app setting by hand, in which
  case that hand-set `false` still wins and must be removed deliberately.
- Three facts on one cell means three answers to "is this person competent?",
  and callers must say which they mean. That is the point: a single merged
  boolean is the failure mode this ADR exists to prevent.
- ISO 45001 7.2 and ISO 9001 7.2 evidence stays where it is retained today —
  PAMS for issuance, Citation for statutory training, QGP for the assessment it
  actually ran. QGP adds a third piece of evidence; it does not become the
  register of the other two.
- An empty `demonstrated` overlay is the normal state for most cells for as long
  as most characteristics have no bound assessment. That is honest and is not a
  gap to be filled by defaulting.

## Out of scope

- Any PAMS or Citation write path, and any mark-competent control on a cell.
- CompetencyDashboard rewrite, and any Finder / Guardian / Coach surface.
- Bulk QGP User creation for Atlas people. Fuzzy name joins.
- Per-person compliance-schedule rows for training (ADR-0020 kill).
- Entra attestation — `ENTRA_ATTESTATION_ENABLED` stays false.
- ISO 14001:2026 S0. Voyage V0.

## References

- CB-PR1 #1827 · CB-PR2 #1828 · CB-PR3 #1829 · CB-PR4 #1832 · CB-PR5 #1833 ·
  this PR (CB-PR6)
- ADR-0020 — compliance schedule occurrence model
- `src/core/config.py` — `competence_board_enabled`
- `src/api/routes/workforce_competence_board.py` —
  `require_competence_board_enabled`
- `src/domain/services/competence_demonstration_service.py` — overlay, never a
  PAMS write
