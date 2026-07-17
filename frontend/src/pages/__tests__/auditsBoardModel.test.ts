import { describe, expect, it } from 'vitest'
import type { AuditRun } from '../../api/client'
import {
  BOARD_STATUS_IDS,
  BOARD_WORK_LANES,
  PROGRAM_FILTER_CHIPS,
  classifyAuditProgram,
  getAuditsForLaneStatuses,
} from '../auditsBoardModel'

function run(partial: Partial<AuditRun> & Pick<AuditRun, 'id' | 'status'>): AuditRun {
  return {
    reference_number: `AUD-${partial.id}`,
    template_id: 1,
    template_version: 1,
    title: `Audit ${partial.id}`,
    created_at: '2026-07-12T10:00:00Z',
    source_origin: 'internal',
    ...partial,
  } as AuditRun
}

describe('AUD-W-01 audits board model (Round 3)', () => {
  it('locks exactly three work lanes (not equal 4-col status board)', () => {
    expect(BOARD_WORK_LANES).toHaveLength(3)
    expect(BOARD_WORK_LANES.map((lane) => lane.id)).toEqual(['do_now', 'review', 'closed'])
    expect(BOARD_WORK_LANES.map((lane) => lane.label)).toEqual([
      'Do now',
      'Needs review',
      'Closed',
    ])
  })

  it('aggregates scheduled + in_progress into Do now', () => {
    const doNow = BOARD_WORK_LANES.find((lane) => lane.id === 'do_now')
    expect(doNow?.statuses).toEqual(['scheduled', 'in_progress'])
    expect(BOARD_STATUS_IDS.has('scheduled')).toBe(true)
    expect(BOARD_STATUS_IDS.has('in_progress')).toBe(true)
    expect(BOARD_STATUS_IDS.has('draft')).toBe(false)
    expect(BOARD_STATUS_IDS.has('cancelled')).toBe(false)
  })

  it('groups mixed statuses into the Round 3 lanes', () => {
    const audits = [
      run({ id: 1, status: 'scheduled', title: 'Scheduled' }),
      run({ id: 2, status: 'in_progress', title: 'In progress' }),
      run({ id: 3, status: 'pending_review', title: 'Review' }),
      run({ id: 4, status: 'completed', title: 'Done' }),
      run({ id: 5, status: 'draft', title: 'Draft' }),
    ]

    const doNow = getAuditsForLaneStatuses(audits, BOARD_WORK_LANES[0].statuses)
    const review = getAuditsForLaneStatuses(audits, BOARD_WORK_LANES[1].statuses)
    const closed = getAuditsForLaneStatuses(audits, BOARD_WORK_LANES[2].statuses)

    expect(doNow.map((a) => a.title)).toEqual(['Scheduled', 'In progress'])
    expect(review.map((a) => a.title)).toEqual(['Review'])
    expect(closed.map((a) => a.title)).toEqual(['Done'])
  })

  it('exposes program chips for Internal / UVDB / Planet Mark / Customer', () => {
    expect(PROGRAM_FILTER_CHIPS.map((chip) => chip.id)).toEqual([
      'internal',
      'uvdb',
      'planet_mark',
      'customer',
    ])
  })

  it('classifies program slices for chip filtering', () => {
    expect(
      classifyAuditProgram(run({ id: 1, status: 'scheduled', source_origin: 'internal' })),
    ).toBe('internal')
    expect(
      classifyAuditProgram(
        run({
          id: 2,
          status: 'pending_review',
          source_origin: 'third_party',
          assurance_scheme: 'Achilles UVDB',
          is_external_audit_import: true,
        } as Partial<AuditRun> & Pick<AuditRun, 'id' | 'status'>),
      ),
    ).toBe('uvdb')
    expect(
      classifyAuditProgram(
        run({
          id: 3,
          status: 'completed',
          assurance_scheme: 'Planet Mark Year 1',
          external_audit_type: 'planet_mark',
        } as Partial<AuditRun> & Pick<AuditRun, 'id' | 'status'>),
      ),
    ).toBe('planet_mark')
    expect(
      classifyAuditProgram(
        run({
          id: 4,
          status: 'scheduled',
          source_origin: 'customer',
          assurance_scheme: 'Customer Audit',
        }),
      ),
    ).toBe('customer')
  })
})
