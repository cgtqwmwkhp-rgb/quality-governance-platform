import { describe, expect, it } from 'vitest'
import {
  countOpenAuditFindings,
  findingMatchesClause,
  findingsEmptyNamesProgram,
  formatFindingsTruncation,
  isOpenAuditFinding,
  resolveOpenFindingsKpi,
  scopeFindingsToRunIds,
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

describe('A3 findings scope + clause', () => {
  it('does not use the tenant server total when the view is a subset', () => {
    const loaded = [
      { id: 1, status: 'open', run_id: 1 },
      { id: 2, status: 'open', run_id: 1 },
    ] as const
    expect(
      resolveOpenFindingsKpi(loaded, 100, 101, { useServerTotalWhenTruncated: false }),
    ).toBe(2)
  })

  it('keeps findings whose run_id is in the programme set', () => {
    const findings = [
      { id: 1, run_id: 10, status: 'open' },
      { id: 2, run_id: 99, status: 'open' },
    ] as const
    expect(scopeFindingsToRunIds(findings, new Set([10])).map((finding) => finding.id)).toEqual([
      1,
    ])
  })

  it('matches import-style clause_ids and bounded title mentions, not integer catalog ids', () => {
    expect(findingMatchesClause({ clause_ids: ['7.2'] }, '7.2')).toBe(true)
    expect(findingMatchesClause({ clause_ids: ['7.2'] }, ' 7.2 ')).toBe(true)
    expect(findingMatchesClause({ clause_ids: ['8.1'] }, '7.2')).toBe(false)
    expect(findingMatchesClause({ clause_ids: [72] }, '7.2')).toBe(false)
    expect(findingMatchesClause({ title: 'Competence 7.2 training' }, '7.2')).toBe(true)
    expect(findingMatchesClause({ title: 'Clause 17.2 leftover' }, '7.2')).toBe(false)
    expect(findingMatchesClause({ clause_ids: ['7.2'] }, '')).toBe(true)
  })
})

describe('N2 findings follow-up honesty', () => {
  it('names empty copy only when a programme chip is active', () => {
    expect(findingsEmptyNamesProgram('all')).toBe(false)
    expect(findingsEmptyNamesProgram('planet_mark')).toBe(true)
    expect(findingsEmptyNamesProgram('internal')).toBe(true)
  })

  it('formats tenant-wide truncation like N1 runs', () => {
    expect(formatFindingsTruncation(1, 101)).toBe('Showing 1 of 101 findings')
  })
})
