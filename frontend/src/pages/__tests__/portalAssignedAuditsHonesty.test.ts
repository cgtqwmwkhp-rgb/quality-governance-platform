import { describe, expect, it } from 'vitest'
import {
  assignedAuditQueueTotal,
  isShowableAssignedAudit,
} from '../portalAssignedAuditsHonesty'

describe('portal assigned-audit honesty', () => {
  it('hides serializer-fallback and closed rows', () => {
    expect(
      isShowableAssignedAudit({ reference_number: 'AUD-1', status: 'scheduled' }),
    ).toBe(true)
    expect(isShowableAssignedAudit({ reference_number: '???', status: 'scheduled' })).toBe(false)
    expect(isShowableAssignedAudit({ reference_number: 'AUD-1', status: 'unknown' })).toBe(false)
    expect(isShowableAssignedAudit({ reference_number: 'AUD-1', status: 'completed' })).toBe(false)
  })

  it('never returns a fake zero when the server total is missing or the load failed', () => {
    expect(assignedAuditQueueTotal(0, false)).toBe(0)
    expect(assignedAuditQueueTotal(3, false)).toBe(3)
    expect(assignedAuditQueueTotal(0, true)).toBeNull()
    expect(assignedAuditQueueTotal(undefined, false)).toBeNull()
  })
})
