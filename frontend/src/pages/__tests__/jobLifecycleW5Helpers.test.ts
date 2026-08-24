import { describe, expect, it } from 'vitest'
import {
  baselineViewingBanner,
  portalCycleIsReadOnly,
  portalNestTargets,
  shouldShowBaselineBanner,
  summariseBaselineDiff,
} from '../jobLifecycleHelpers'
import type { JobTypeBaselineDiffResponse, PortalNestedCycleResponse } from '../../api/jobLifecycleClient'

describe('JL-UX-W5 helpers', () => {
  it('baseline banner keeps edit on the live tip', () => {
    const copy = baselineViewingBanner({ id: 9, label: 'Approved' })
    expect(copy).toContain('#9')
    expect(copy).toContain('Approved')
    expect(copy.toLowerCase()).toContain('live tip')
  })

  it('shows the banner only when a baseline id is selected', () => {
    expect(shouldShowBaselineBanner(null)).toBe(false)
    expect(shouldShowBaselineBanner(3)).toBe(true)
  })

  it('summarises structured diff counts', () => {
    const diff = {
      has_changes: true,
      summary: {
        lanes: { added: 1, removed: 0, changed: 2 },
        steps: { added: 0, removed: 0, changed: 0 },
      },
    } as JobTypeBaselineDiffResponse
    expect(summariseBaselineDiff(diff)).toContain('lanes: +1')
    expect(summariseBaselineDiff({ ...diff, has_changes: false })).toContain('matches')
  })

  it('portal payload is treated as read-only unless author is explicitly true', () => {
    expect(portalCycleIsReadOnly(null)).toBe(true)
    expect(
      portalCycleIsReadOnly({ read_only: true, can_author: false } as PortalNestedCycleResponse),
    ).toBe(true)
    expect(
      portalCycleIsReadOnly({ read_only: false, can_author: true } as PortalNestedCycleResponse),
    ).toBe(false)
  })

  it('collects nest targets from portal cells', () => {
    const targets = portalNestTargets([
      {
        id: 1,
        lane_id: 2,
        step_id: 3,
        requires_evidence: false,
        library_document_ids: [],
        nest_links: [
          {
            id: 10,
            kind: 'job_cycle',
            label: 'Engineer',
            target_job_type_id: 44,
            href: '/job-lifecycle/cycles/44',
            sort_order: 0,
          },
        ],
      },
    ])
    expect(targets).toEqual([
      {
        cellId: 1,
        laneId: 2,
        stepId: 3,
        targetJobTypeId: 44,
        label: 'Engineer',
      },
    ])
  })
})
