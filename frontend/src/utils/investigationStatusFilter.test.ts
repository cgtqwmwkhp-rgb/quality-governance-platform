import { describe, expect, it } from 'vitest'
import {
  ALL_STATUS_VALUES,
  getEnabledFilterOptions,
  getFilterOption,
  getStatusDisplay,
  getStatusValuesForFilter,
  statusMatchesFilter,
} from './investigationStatusFilter'

describe('investigationStatusFilter', () => {
  it('resolves filter options and enabled list', () => {
    expect(getFilterOption('open')?.values).toEqual(['draft', 'in_progress'])
    expect(getFilterOption('cancelled')?.disabled).toBe(true)
    expect(getEnabledFilterOptions().every((o) => !o.disabled)).toBe(true)
  })

  it('maps filter ids to backend statuses', () => {
    expect(getStatusValuesForFilter('all')).toEqual([])
    expect(getStatusValuesForFilter('pending_review')).toEqual(['under_review'])
    expect(getStatusValuesForFilter('nope')).toEqual([])
  })

  it('statusMatchesFilter handles all vs specific', () => {
    expect(statusMatchesFilter('draft', 'all')).toBe(true)
    expect(statusMatchesFilter('draft', 'cancelled')).toBe(false)
    expect(statusMatchesFilter('draft', 'open')).toBe(true)
    expect(statusMatchesFilter('closed', 'open')).toBe(false)
  })

  it('getStatusDisplay covers known and unknown', () => {
    expect(getStatusDisplay('draft').label).toBe('Draft')
    expect(getStatusDisplay('weird_status').label).toBe('Weird Status')
    expect(ALL_STATUS_VALUES).toContain('under_review')
  })
})
