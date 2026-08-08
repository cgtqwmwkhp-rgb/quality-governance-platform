/**
 * JL-UX-W2 helpers — PDCA colouring, derived nesting, breadcrumb, reorder.
 *
 * The load-bearing claims: the lane nest chip is *derived* from `job_cycle`
 * links (there is no lane FK to read), and an unset PDCA phase stays unset
 * rather than defaulting to `plan`.
 */
import { describe, expect, it } from 'vitest'
import type { JobCell, JobStep, JobType } from '../../api/jobLifecycleClient'
import {
  buildJobCycleBreadcrumb,
  computeAxisReorder,
  deriveLaneNestChips,
  deriveNestedJobTypeIds,
  isJobStepPdcaPhase,
  nextPdcaPhase,
  pdcaPhaseClasses,
  pdcaPhaseLabel,
  pushDrillTrail,
  resolvePdcaPhase,
  shouldShowJobCycleBreadcrumb,
  truncateDrillTrail,
} from '../jobLifecycleHelpers'

const NOW = '2026-08-08T00:00:00Z'

function jobType(id: number, name: string, sortOrder = 0): JobType {
  return {
    id,
    tenant_id: 1,
    code: name.toLowerCase().replace(/\s+/g, '_'),
    name,
    sort_order: sortOrder,
    is_active: true,
    created_at: NOW,
    updated_at: NOW,
  }
}

function step(id: number, name: string, sortOrder: number): JobStep {
  return {
    id,
    tenant_id: 1,
    job_type_id: 1,
    code: name.toLowerCase(),
    name,
    sort_order: sortOrder,
    is_active: true,
    created_at: NOW,
    updated_at: NOW,
  }
}

function cellWithNest(laneId: number, stepId: number, targets: number[]): JobCell {
  return {
    id: laneId * 100 + stepId,
    tenant_id: 1,
    job_type_id: 1,
    lane_id: laneId,
    step_id: stepId,
    library_document_ids: [],
    links: targets.map((target, index) => ({
      id: laneId * 1000 + stepId * 10 + index,
      tenant_id: 1,
      cell_id: laneId * 100 + stepId,
      kind: 'job_cycle' as const,
      label: `Nested ${target}`,
      target_job_type_id: target,
      href: `/job-lifecycle/cycles/${target}`,
      sort_order: index,
      created_at: NOW,
      updated_at: NOW,
    })),
    created_at: NOW,
    updated_at: NOW,
  }
}

describe('PDCA phase helpers', () => {
  it('accepts only the four Deming phases', () => {
    expect(isJobStepPdcaPhase('plan')).toBe(true)
    expect(isJobStepPdcaPhase('do')).toBe(true)
    expect(isJobStepPdcaPhase('check')).toBe(true)
    expect(isJobStepPdcaPhase('act')).toBe(true)
    expect(isJobStepPdcaPhase('review')).toBe(false)
    expect(isJobStepPdcaPhase(null)).toBe(false)
  })

  it('reads tolerantly and never invents a default phase', () => {
    expect(resolvePdcaPhase('PLAN')).toBe('plan')
    expect(resolvePdcaPhase('  act  ')).toBe('act')
    expect(resolvePdcaPhase(null)).toBeNull()
    expect(resolvePdcaPhase(undefined)).toBeNull()
    expect(resolvePdcaPhase('nonsense')).toBeNull()
    expect(resolvePdcaPhase(7)).toBeNull()
  })

  it('gives every phase a distinct colour and unset a neutral one', () => {
    const phases = ['plan', 'do', 'check', 'act'] as const
    const classes = phases.map((phase) => pdcaPhaseClasses(phase))
    expect(new Set(classes).size).toBe(4)
    const unset = pdcaPhaseClasses(null)
    expect(classes).not.toContain(unset)
    expect(unset).toContain('muted')
  })

  it('labels an unset phase honestly', () => {
    expect(pdcaPhaseLabel(null)).toBe('No phase')
    expect(pdcaPhaseLabel('check')).toBe('Check')
  })

  it('cycles plan → do → check → act → unset', () => {
    expect(nextPdcaPhase(null)).toBe('plan')
    expect(nextPdcaPhase('plan')).toBe('do')
    expect(nextPdcaPhase('do')).toBe('check')
    expect(nextPdcaPhase('check')).toBe('act')
    expect(nextPdcaPhase('act')).toBeNull()
  })
})

describe('nesting derived from job_cycle links', () => {
  it('derives lane chips from the lane’s cells only', () => {
    const cells = [cellWithNest(10, 20, [2]), cellWithNest(11, 20, [3])]
    const chips = deriveLaneNestChips(cells, 10, [jobType(2, 'Engineer')])
    expect(chips).toEqual([{ targetJobTypeId: 2, label: 'Engineer' }])
    expect(deriveLaneNestChips(cells, 11, [])).toEqual([
      { targetJobTypeId: 3, label: 'Nested 3' },
    ])
  })

  it('dedupes a cycle nested from several cells in one lane', () => {
    const cells = [cellWithNest(10, 20, [2]), cellWithNest(10, 21, [2])]
    expect(deriveLaneNestChips(cells, 10, [jobType(2, 'Engineer')])).toHaveLength(1)
  })

  it('returns nothing for a lane with no nest links', () => {
    expect(deriveLaneNestChips([cellWithNest(10, 20, [])], 10, [])).toEqual([])
    expect(deriveLaneNestChips([], 10, [])).toEqual([])
  })

  it('ignores non-nest kinds and malformed targets', () => {
    const cell: JobCell = {
      ...cellWithNest(10, 20, []),
      links: [
        {
          id: 1,
          tenant_id: 1,
          cell_id: 1,
          kind: 'app',
          label: 'Doc',
          entity_type: 'document',
          entity_id: 5,
          href: '/documents/5',
          sort_order: 0,
          created_at: NOW,
          updated_at: NOW,
        },
        {
          id: 2,
          tenant_id: 1,
          cell_id: 1,
          kind: 'job_cycle',
          label: 'Broken',
          target_job_type_id: null,
          href: '#',
          sort_order: 1,
          created_at: NOW,
          updated_at: NOW,
        },
      ],
    }
    expect(deriveLaneNestChips([cell], 10, [])).toEqual([])
  })

  it('collects every nested cycle across the pack', () => {
    const cells = [cellWithNest(10, 20, [2, 3]), cellWithNest(11, 21, [3, 4])]
    expect(deriveNestedJobTypeIds(cells)).toEqual([2, 3, 4])
  })
})

describe('drill-in / drill-out breadcrumb', () => {
  it('is hidden until there is somewhere to drill back out to', () => {
    expect(shouldShowJobCycleBreadcrumb([])).toBe(false)
    expect(shouldShowJobCycleBreadcrumb([1])).toBe(true)
  })

  it('pushes the cycle being left, ignoring repeats and bad ids', () => {
    expect(pushDrillTrail([], 1)).toEqual([1])
    expect(pushDrillTrail([1], 2)).toEqual([1, 2])
    expect(pushDrillTrail([1], 1)).toEqual([1])
    expect(pushDrillTrail([1], null)).toEqual([1])
    expect(pushDrillTrail([1], 0)).toEqual([1])
    expect(pushDrillTrail([1], -3)).toEqual([1])
  })

  it('truncates to the chosen ancestor, discarding deeper entries', () => {
    expect(truncateDrillTrail([1, 2, 3], 0)).toEqual([])
    expect(truncateDrillTrail([1, 2, 3], 1)).toEqual([1])
    expect(truncateDrillTrail([1, 2, 3], 2)).toEqual([1, 2])
    expect(truncateDrillTrail([1, 2, 3], -1)).toEqual([])
  })

  it('marks only the last item as current and names cycles from the pack', () => {
    const items = buildJobCycleBreadcrumb({
      trail: [1, 2],
      currentJobTypeId: 3,
      jobTypes: [jobType(1, 'Operational'), jobType(2, 'Engineer'), jobType(3, 'Commissioning')],
    })
    expect(items.map((i) => i.label)).toEqual(['Operational', 'Engineer', 'Commissioning'])
    expect(items.map((i) => i.isCurrent)).toEqual([false, false, true])
  })

  it('falls back to an id label for a cycle not in the loaded list', () => {
    const items = buildJobCycleBreadcrumb({ trail: [], currentJobTypeId: 42, jobTypes: [] })
    expect(items).toEqual([{ jobTypeId: 42, label: 'Job cycle #42', isCurrent: true }])
  })

  it('yields an empty breadcrumb when no cycle is selected', () => {
    expect(buildJobCycleBreadcrumb({ trail: [], currentJobTypeId: null, jobTypes: [] })).toEqual([])
  })
})

describe('axis reorder over the existing PATCH APIs', () => {
  const steps = [step(1, 'Alpha', 0), step(2, 'Bravo', 1), step(3, 'Charlie', 2)]

  it('moves an item up and renumbers densely', () => {
    expect(computeAxisReorder(steps, 2, 'up')).toEqual([
      { id: 2, sort_order: 0 },
      { id: 1, sort_order: 1 },
    ])
  })

  it('moves an item down', () => {
    expect(computeAxisReorder(steps, 2, 'down')).toEqual([
      { id: 3, sort_order: 1 },
      { id: 2, sort_order: 2 },
    ])
  })

  it('issues no writes at the ends of the list', () => {
    expect(computeAxisReorder(steps, 1, 'up')).toEqual([])
    expect(computeAxisReorder(steps, 3, 'down')).toEqual([])
  })

  it('issues no writes for an unknown id', () => {
    expect(computeAxisReorder(steps, 999, 'up')).toEqual([])
  })

  it('still moves items when stored sort_order values are all equal', () => {
    const tied = [step(1, 'Alpha', 0), step(2, 'Bravo', 0), step(3, 'Charlie', 0)]
    const updates = computeAxisReorder(tied, 3, 'up')
    // Ties break by name, so the order is Alpha, Bravo, Charlie; moving
    // Charlie up must actually change positions rather than swap 0 with 0.
    expect(updates).toEqual([
      { id: 3, sort_order: 1 },
      { id: 2, sort_order: 2 },
    ])
  })

  it('handles sparse sort_order values', () => {
    const sparse = [step(1, 'Alpha', 5), step(2, 'Bravo', 90)]
    expect(computeAxisReorder(sparse, 2, 'up')).toEqual([
      { id: 2, sort_order: 0 },
      { id: 1, sort_order: 1 },
    ])
  })
})
