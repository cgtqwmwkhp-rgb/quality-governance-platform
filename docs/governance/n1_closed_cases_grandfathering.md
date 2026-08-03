# N-1: closed cases that predate the closure gate

Owner: **Jamie Uncle** (QHSE / operations). Platform holds the measurement and the
code; the business decision is recorded below.

Tracking: PX-333 in `docs/uat/QGP-Run021-Defect-Log.csv`, under GitHub issue #1522
(walk-away definition B).

## The gate that now exists

`src/domain/services/case_closure.py` refuses a close that does not meet the
standard, on every case type — incident, complaint, near miss, road traffic
collision — and refuses it in the service layer rather than the UI, so every
close path (detail page, edit form, API client, script) hits the same check.
Investigations have their own richer equivalent in
`investigation_closure_helpers.py`.

Three reason codes:

| Code | Meaning |
| --- | --- |
| `INVALID_STATE_TRANSITION` | the current status cannot move straight to closed |
| `MISSING_LESSONS_LEARNT` | `lessons_learnt` is empty once trimmed |
| `OPEN_ACTIONS_REMAIN` | CAPAs or actions on the case are neither completed nor cancelled |

The readiness endpoint reports the same codes as the write path refuses under,
so the UI can never tell a user a case is closable and then have the close fail.

## The estate that predates it

Measured against production on **2026-07-28**, before the gate was in force:

- **84 closed cases** hold no lessons learnt.
- **3 incidents** were closed with actions still incomplete.

Every one of these was closed legitimately under the standard that applied at
the time. The gate is new; the records are not defective by the rule they were
created under.

## The position, stated plainly

**Historic closed cases are grandfathered. Nothing retro-validates them, and
nothing has been back-filled, force-closed, reopened or edited to satisfy the
new gate.**

That is a deliberate choice, not an oversight, and it is the conservative one
for exactly the reason the gate exists: `lessons_learnt` on a closed governance
record is evidence. Writing a plausible sentence into 84 of them so a report
turns green would manufacture evidence that no one learnt anything from, on
records that may be cited in an audit. #1398 settled the same principle for
attribution — a bulk operation does not invent a field whose value it does not
know.

So the current, accurate statement of the position is:

1. **New closes meet the standard.** Enforced in the service layer, not
   advisory.
2. **Old closes are as they were.** They are visible as non-conforming to the
   current gate, and that visibility is the point.
3. **There is no waiver mechanism for cases.** The investigation close path has
   `allow_override` with a recorded reason; the case close path has no
   equivalent, so nothing can be closed today with a note saying the gate was
   skipped. If per-case grandfathering is ever wanted as a first-class state,
   it has to be built, not improvised.

## The trap: reopen and re-close

A grandfathered case is only grandfathered while it stays closed. The gate is on
the **close transition**, so reopening a historic case and closing it again puts
it through the current standard, and it will be refused under
`MISSING_LESSONS_LEARNT` if it still has none.

This is correct behaviour and should not be softened. It does mean a user
touching an old case for an unrelated reason can find themselves unable to put
it back — and that they must then write the lessons learnt for an event that may
be a year old, from whatever record survives. Anyone reopening a pre-gate case
should expect to do that, or should not reopen it.

## Decision locked (2026-08-03)

**Accept the estate as it stands.** David Harris directed that **all** historic
closed cases below the current gate are grandfathered — keep every one as
historical; do not remediate en masse and do not invent lessons learnt.

| Field | Value |
| --- | --- |
| Who | David Harris (programme) |
| When | 2026-08-03 |
| Count at measurement | 84 closed without lessons learnt; 3 incidents closed with incomplete actions (prod 2026-07-28) |
| Written rule owner | Jamie Uncle — keep this note as the auditor-facing answer |
| Code change | None — no back-fill, no force-close, no fabricated evidence |

**What must not happen** is a bulk `UPDATE` that puts placeholder text into
`lessons_learnt`, or a migration that marks the three incidents' actions
complete. Either one converts "we know these 84 records predate the standard"
into "these 84 records meet the standard", which is a false statement in a
compliance system, and it is unrecoverable — the original state is gone.

The 84 cases and the 3 incidents remain as they were on 2026-07-28 unless
someone has since worked them case-by-case. Re-measure before citing the numbers.
