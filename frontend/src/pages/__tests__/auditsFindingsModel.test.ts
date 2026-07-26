import { describe, expect, it } from 'vitest'
import {
  countOpenAuditFindings,
  isOpenAuditFinding,
  resolveOpenFindingsKpi,
} from '../auditsFindingsModel'

describe('auditsFindingsModel (PX-262)', () => {
  it('treats actionable non-closed statuses as open', () => {
    expect(isOpenAuditFinding('open')).toBe(true)
    expect(isOpenAuditFinding('IN_PROGRESS')).toBe(true)
    expect(isOpenAuditFinding('pending_verification')).toBe(true)
    expect(isOpenAuditFinding('deferred')).toBe(true)
    expect(isOpenAuditFinding('closed')).toBe(false)
  })

  it('counts open findings in a loaded slice', () => {
    const findings = [
      { id: 1, status: 'open' },
      { id: 2, status: 'closed' },
      { id: 3, status: 'in_progress' },
    ] as const

    expect(countOpenAuditFindings(findings)).toBe(2)
  })

  it('prefers the server open total when the findings page is truncated', () => {
    const loaded = [{ id: 1, status: 'open' }] as const
    expect(resolveOpenFindingsKpi(loaded, 100, 101)).toBe(100)
  })

  it('falls back to the loaded slice when no server total is available', () => {
    const loaded = [
      { id: 1, status: 'open' },
      { id: 2, status: 'open' },
    ] as const
    expect(resolveOpenFindingsKpi(loaded, null, null)).toBe(2)
  })
})
