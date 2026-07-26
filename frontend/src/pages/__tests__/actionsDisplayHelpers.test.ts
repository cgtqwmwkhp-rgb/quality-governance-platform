import { describe, expect, it } from 'vitest'
import { formatActionSourceRef, isInternalSourceReference } from '../actionsDisplayHelpers'

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
