import { describe, expect, it } from 'vitest'
import {
  PEOPLE_CELL_TONE,
  PLANT_CELL_TONE,
  apiErrorStatus,
  peopleCellState,
  peopleCellSummary,
  plantCellState,
  plantCellSummary,
  todayIso,
} from './competenceBoardCells'

const TODAY = '2026-09-03'

describe('plantCellState', () => {
  it('treats an absent characteristic as no record, not a failure', () => {
    expect(plantCellState(undefined, TODAY)).toBe('no_record')
  })

  it('keeps an issued-but-unassessed cell as issued', () => {
    expect(plantCellState({ issued: true }, TODAY)).toBe('issued')
  })

  it('reads the CB-PR4 overlay when a bound assessment passed', () => {
    expect(plantCellState({ issued: true, demonstrated: 'pass' }, TODAY)).toBe('demonstrated_pass')
  })

  it('reads a recorded fail as a fail', () => {
    expect(plantCellState({ issued: true, demonstrated: 'fail' }, TODAY)).toBe('demonstrated_fail')
  })

  it('falls back to issued — not fail — when the demonstration has lapsed', () => {
    expect(
      plantCellState(
        { issued: true, demonstrated: 'pass', demonstrated_expires_on: '2026-08-31' },
        TODAY,
      ),
    ).toBe('issued')
  })

  it('keeps a demonstration that expires today as a pass', () => {
    expect(
      plantCellState(
        { issued: true, demonstrated: 'pass', demonstrated_expires_on: TODAY },
        TODAY,
      ),
    ).toBe('demonstrated_pass')
  })

  it('does not invent an issue from a cell PAMS did not issue', () => {
    expect(plantCellState({ issued: false }, TODAY)).toBe('no_record')
  })
})

describe('plant cell tones', () => {
  // The old workshop matrix painted not_assessed with bg-muted-foreground/40,
  // which reported "QGP has not assessed this" as if it were a competence
  // failure. Neither unassessed state may carry a fail or grey-blocked fill.
  it.each(['no_record', 'issued'] as const)('does not paint %s as a failure', (state) => {
    expect(PLANT_CELL_TONE[state]).not.toMatch(/bg-destructive/)
    expect(PLANT_CELL_TONE[state]).not.toMatch(/bg-muted-foreground/)
  })

  it('reserves the destructive fill for a recorded fail', () => {
    expect(PLANT_CELL_TONE.demonstrated_fail).toMatch(/bg-destructive/)
  })
})

describe('plantCellSummary', () => {
  it('says what an unassessed issued cell actually means', () => {
    expect(plantCellSummary('Counterbalance FLT', { issued: true }, TODAY)).toBe(
      'Counterbalance FLT — issued in PAMS, not demonstrated in QGP',
    )
  })

  it('names the source of a no-record cell', () => {
    expect(plantCellSummary('Counterbalance FLT', undefined, TODAY)).toContain('no PAMS record')
  })

  it('explains a lapsed demonstration rather than dropping it silently', () => {
    expect(
      plantCellSummary(
        'Counterbalance FLT',
        { issued: true, demonstrated: 'pass', demonstrated_expires_on: '2026-08-31' },
        TODAY,
      ),
    ).toContain('previous QGP demonstration expired 2026-08-31')
  })

  it('carries thorough examination when PAMS recorded it', () => {
    expect(plantCellSummary('Crane', { issued: true, thorough_exam: true }, TODAY)).toContain(
      'thorough examination recorded',
    )
  })
})

describe('peopleCellState', () => {
  it('treats an absent course as no record', () => {
    expect(peopleCellState(undefined, TODAY)).toBe('no_record')
  })

  it('marks an in-date pass as passed', () => {
    expect(
      peopleCellState({ issued: true, passed_on: '2026-01-04', expires_on: '2027-01-04' }, TODAY),
    ).toBe('passed')
  })

  it('marks a lapsed pass as expired rather than as a pass', () => {
    expect(
      peopleCellState({ issued: true, passed_on: '2023-01-04', expires_on: '2026-01-04' }, TODAY),
    ).toBe('passed_expired')
  })

  it('surfaces an Atlas expiry that has no pass date', () => {
    expect(peopleCellState({ issued: false, expires_on: '2027-01-04' }, TODAY)).toBe(
      'expiry_without_pass',
    )
  })

  it('does not invent a state for a row with neither pass nor expiry', () => {
    expect(peopleCellState({ issued: false }, TODAY)).toBe('no_record')
  })
})

describe('people cell tones', () => {
  it.each(['no_record', 'expiry_without_pass'] as const)(
    'does not paint %s as a failure',
    (state) => {
      expect(PEOPLE_CELL_TONE[state]).not.toMatch(/bg-destructive/)
      expect(PEOPLE_CELL_TONE[state]).not.toMatch(/bg-muted-foreground/)
    },
  )
})

describe('peopleCellSummary', () => {
  it('reports the expiry conflict in words', () => {
    expect(peopleCellSummary('Fire Marshal', { issued: false, expires_on: '2027-01-04' }, TODAY)).toBe(
      'Fire Marshal — Atlas holds an expiry of 2027-01-04 with no pass date',
    )
  })

  it('does not claim a pass date it does not have', () => {
    expect(peopleCellSummary('Fire Marshal', { issued: true }, TODAY)).toContain(
      'passed on an unrecorded date',
    )
  })
})

describe('todayIso', () => {
  it('formats the local calendar date, not a UTC shift', () => {
    // 23:30 local on 3 Sep is 3 Sep locally whatever the offset does to UTC.
    expect(todayIso(new Date(2026, 8, 3, 23, 30))).toBe('2026-09-03')
  })
})

describe('apiErrorStatus', () => {
  it('reads an axios-shaped status without depending on axios', () => {
    expect(apiErrorStatus({ response: { status: 404 } })).toBe(404)
  })

  it('returns null for a network error with no response', () => {
    expect(apiErrorStatus(new Error('Network Error'))).toBeNull()
    expect(apiErrorStatus(null)).toBeNull()
    expect(apiErrorStatus({ response: { status: '404' } })).toBeNull()
  })
})
