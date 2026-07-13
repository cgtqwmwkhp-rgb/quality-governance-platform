import { describe, expect, it } from 'vitest'
import {
  actionsViewRequiresIdentity,
  actionsViewUsesServerFilter,
  buildActionsListScope,
  parseActionsViewParam,
} from '../actionsViewScope'

describe('actionsViewScope', () => {
  it('parses view query values and defaults unknown to all', () => {
    expect(parseActionsViewParam('my')).toBe('my')
    expect(parseActionsViewParam('overdue')).toBe('overdue')
    expect(parseActionsViewParam('my_overdue')).toBe('my_overdue')
    expect(parseActionsViewParam(null)).toBe('all')
    expect(parseActionsViewParam('nope')).toBe('all')
  })

  it('builds assigned_to / overdue scope for each view mode', () => {
    expect(buildActionsListScope('all')).toEqual({
      assigned_to: undefined,
      overdue: undefined,
    })
    expect(buildActionsListScope('my')).toEqual({
      assigned_to: 'me',
      overdue: undefined,
    })
    expect(buildActionsListScope('overdue')).toEqual({
      assigned_to: undefined,
      overdue: true,
    })
    expect(buildActionsListScope('my_overdue')).toEqual({
      assigned_to: 'me',
      overdue: true,
    })
  })

  it('flags identity + server-filter requirements', () => {
    expect(actionsViewRequiresIdentity('my')).toBe(true)
    expect(actionsViewRequiresIdentity('my_overdue')).toBe(true)
    expect(actionsViewRequiresIdentity('overdue')).toBe(false)
    expect(actionsViewUsesServerFilter('all')).toBe(false)
    expect(actionsViewUsesServerFilter('overdue')).toBe(true)
  })
})
