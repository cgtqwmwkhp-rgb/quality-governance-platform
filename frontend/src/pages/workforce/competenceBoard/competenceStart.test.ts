import { describe, expect, it } from 'vitest'
import type { CompetenceBoardColumn } from '../../../api/competenceBoardClient'
import {
  CANNOT_ASSESS_SELF,
  NOT_PLANT_FAMILY,
  NO_FAMILY_TEMPLATE,
  PERSON_NOT_LINKED,
  boundModes,
  cellStartability,
  defaultMode,
  isUnbound,
  normaliseEvidence,
  startabilitySummary,
} from './competenceStart'

const BOUND: CompetenceBoardColumn = {
  key: 'COUNTERBALANCE_FLT',
  label: 'COUNTERBALANCE_FLT',
  bound_modes: ['field', 'induction'],
}

const UNBOUND: CompetenceBoardColumn = { key: 'MEWP_3A', label: 'MEWP_3A', bound_modes: [] }

const ALEX = { engineer_id: 10, mapped: true }
const SAM = {
  engineer_id: 22,
  issued_characteristic_keys: ['COUNTERBALANCE_FLT'],
  blocked_reason: null,
}

function startability(overrides: Partial<Parameters<typeof cellStartability>[0]> = {}) {
  return cellStartability({
    family: 'pams',
    column: BOUND,
    person: ALEX,
    assessor: SAM,
    ...overrides,
  })
}

describe('cellStartability (CB-UI-3)', () => {
  it('lets an issued assessor start either bound mode on someone else', () => {
    expect(startability()).toEqual({ status: 'startable', modes: ['field', 'induction'] })
  })

  it('offers only the mode the bind actually carries', () => {
    expect(startability({ column: { ...BOUND, bound_modes: ['induction'] } })).toEqual({
      status: 'startable',
      modes: ['induction'],
    })
  })

  it('blocks an unbound characteristic as a missing template, never as a failure', () => {
    const result = startability({ column: UNBOUND })

    expect(result).toEqual({ status: 'blocked', reason: NO_FAMILY_TEMPLATE })
    expect(NO_FAMILY_TEMPLATE).not.toMatch(/fail/i)
    expect(NO_FAMILY_TEMPLATE).not.toMatch(/not competent/i)
    // It points at who can fix it, because the reader cannot.
    expect(NO_FAMILY_TEMPLATE).toMatch(/IT-Admin/)
  })

  it('refuses self-assessment', () => {
    expect(startability({ assessor: { ...SAM, engineer_id: 10 } })).toEqual({
      status: 'blocked',
      reason: CANNOT_ASSESS_SELF,
    })
  })

  it('refuses an assessor PAMS has not issued this characteristic to', () => {
    const result = startability({ assessor: { ...SAM, issued_characteristic_keys: ['MEWP_3A'] } })

    expect(result.status).toBe('blocked')
    expect(result).toMatchObject({ reason: expect.stringContaining('PAMS has not issued you') })
    // The sentence must not imply QGP could fix it by writing to PAMS.
    expect(result).toMatchObject({ reason: expect.stringContaining('never writes') })
  })

  it('fails closed on every unprovable assessor, not just on an explicit refusal', () => {
    // No assessor block at all: an older server, or a response that lost it.
    expect(startability({ assessor: undefined }).status).toBe('blocked')
    expect(startability({ assessor: null }).status).toBe('blocked')
    // Present but with nothing in it.
    expect(startability({ assessor: {} }).status).toBe('blocked')
    // Present, has an employee record, but the issued list is missing entirely
    // rather than empty — absence of proof is not proof.
    expect(
      startability({ assessor: { engineer_id: 22, issued_characteristic_keys: null } }).status,
    ).toBe('blocked')
  })

  it('relays the server\u2019s own blocking sentence ahead of guessing one', () => {
    const reason = 'No PAMS competence snapshot has been loaded, so issuance cannot be proven.'

    expect(startability({ assessor: { engineer_id: 22, blocked_reason: reason } })).toEqual({
      status: 'blocked',
      reason,
    })
  })

  it('blocks a PAMS row with no QGP employee record without calling it a gap in competence', () => {
    expect(startability({ person: { engineer_id: null, mapped: false } })).toEqual({
      status: 'blocked',
      reason: PERSON_NOT_LINKED,
    })
    // A row flagged mapped but carrying no id is still unusable, not startable.
    expect(startability({ person: { engineer_id: null, mapped: true } })).toEqual({
      status: 'blocked',
      reason: PERSON_NOT_LINKED,
    })
    expect(PERSON_NOT_LINKED).not.toMatch(/fail/i)
  })

  it('starts nothing on the People family, whatever the payload claims', () => {
    // A bound_modes list on an Atlas column would be a server bug; the board
    // still refuses, because an Atlas course is issued by passing the course.
    expect(startability({ family: 'atlas', column: BOUND })).toEqual({
      status: 'blocked',
      reason: NOT_PLANT_FAMILY,
    })
  })

  it('ranks the unbound column above any fact about the viewer', () => {
    // Both would block. The one that is true for everybody is the useful one:
    // telling Sam "you cannot assess yourself" about a characteristic nobody
    // can assess would send them to the wrong screen.
    const result = startability({ column: UNBOUND, assessor: { ...SAM, engineer_id: 10 } })

    expect(result).toEqual({ status: 'blocked', reason: NO_FAMILY_TEMPLATE })
  })
})

describe('boundModes and isUnbound (CB-UI-3)', () => {
  it('treats an absent bound_modes as unbound rather than as every mode', () => {
    expect(boundModes({ bound_modes: undefined })).toEqual([])
    expect(boundModes({ bound_modes: null })).toEqual([])
    expect(isUnbound({ bound_modes: undefined })).toBe(true)
    expect(isUnbound({ bound_modes: ['field'] })).toBe(false)
  })
})

describe('startabilitySummary (CB-UI-3)', () => {
  it('says what can be started, listing both modes when both are bound', () => {
    expect(startabilitySummary({ status: 'startable', modes: ['field', 'induction'] })).toBe(
      'can start field or induction assessment',
    )
  })

  it('gives the reason verbatim when blocked, so the square is never silently inert', () => {
    expect(startabilitySummary({ status: 'blocked', reason: NO_FAMILY_TEMPLATE })).toBe(
      NO_FAMILY_TEMPLATE,
    )
  })
})

describe('defaultMode (CB-UI-3)', () => {
  it('prefers the field assessment, which is what a plant cell usually means', () => {
    expect(defaultMode(['induction', 'field'])).toBe('field')
  })

  it('falls back to the only bound mode', () => {
    expect(defaultMode(['induction'])).toBe('induction')
  })

  it('does not crash on an empty list, though the form is not reachable then', () => {
    expect(defaultMode([])).toBe('field')
  })
})

describe('normaliseEvidence (CB-UI-3)', () => {
  it('sends nothing at all when the assessor filled nothing in', () => {
    expect(normaliseEvidence({})).toBeNull()
    expect(normaliseEvidence({ make: '', model: '   ', serial: null, pams_plant_id: undefined })).toBeNull()
  })

  it('trims what was typed and omits what was not', () => {
    expect(normaliseEvidence({ make: '  Hyster ', model: '', serial: 'H2-9981' })).toEqual({
      make: 'Hyster',
      serial: 'H2-9981',
    })
  })

  it('keeps a blank box absent rather than recording that it is blank', () => {
    // '' would assert "the serial was checked and is empty". Absent asserts
    // nothing, which is the truth about a box nobody touched.
    const result = normaliseEvidence({ make: 'Hyster', serial: '' })

    expect(result).not.toHaveProperty('serial')
    expect(Object.keys(result ?? {})).toEqual(['make'])
  })
})
