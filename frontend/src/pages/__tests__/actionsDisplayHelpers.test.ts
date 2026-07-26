import { describe, expect, it } from 'vitest'
import {
  formatActionSourceRef,
  isInternalSourceReference,
  resolveActionAssignee,
} from '../actionsDisplayHelpers'

describe('actionsDisplayHelpers', () => {
  it('detects internal storage references', () => {
    expect(isInternalSourceReference('investigation:6')).toBe(true)
    expect(isInternalSourceReference('INC-2026-0020')).toBe(false)
  })

  it('prefers hydrated source_reference over enum fallbacks (PX-152)', () => {
    expect(
      formatActionSourceRef({
        source_type: 'investigation',
        source_id: 6,
        source_reference: 'REF-2026-0006',
      }),
    ).toBe('REF-2026-0006')
  })

  it('falls back to readable label when only internal key exists', () => {
    expect(
      formatActionSourceRef({
        source_type: 'investigation',
        source_id: 6,
        source_reference: 'investigation:6',
      }),
    ).toBe('Investigation #6')
  })
})

describe('resolveActionAssignee (PX-151)', () => {
  it('prefers assigned_to_email over owner_email', () => {
    expect(
      resolveActionAssignee({
        owner_id: 42,
        assigned_to_email: 'lead@example.com',
        owner_email: 'stale@example.com',
      }),
    ).toEqual({ label: 'lead@example.com', state: 'assigned', name: 'lead@example.com' })
  })

  it('falls back to owner_email, which also carries roster-only names', () => {
    const result = resolveActionAssignee({ owner_id: null, owner_email: 'Dai Roberts' })
    expect(result.state).toBe('assigned')
    expect(result.label).toBe('Dai Roberts')
  })

  it('does not report Unassigned when an owner id is present but the name is missing', () => {
    const result = resolveActionAssignee({ owner_id: 42 })
    expect(result.state).toBe('assigned_unnamed')
    expect(result.label).not.toMatch(/unassigned/i)
  })

  it('reports Unassigned only when there is no owner at all', () => {
    expect(resolveActionAssignee({}).state).toBe('unassigned')
    expect(resolveActionAssignee({ owner_id: null }).state).toBe('unassigned')
    expect(resolveActionAssignee({ owner_id: 0 }).state).toBe('unassigned')
  })

  it('treats a whitespace-only email as no name, not as an owner name', () => {
    expect(resolveActionAssignee({ owner_id: 7, assigned_to_email: '   ' }).state).toBe(
      'assigned_unnamed',
    )
    expect(resolveActionAssignee({ assigned_to_email: '   ' }).state).toBe('unassigned')
  })
})
