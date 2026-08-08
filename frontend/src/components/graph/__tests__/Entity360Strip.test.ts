/**
 * Entity360 strip helpers + ImpactBundle → publish preview mapping.
 */
import { describe, expect, it } from 'vitest'
import {
  connectionsHasNeighbors,
  hopCaption,
  shouldFetchEntity360,
  shouldShowEntity360Strip,
} from '../entity360StripHelpers'
import { publishImpactPreviewFromBundle } from '../../../pages/documentPublishImpactHelpers'

describe('entity360StripHelpers', () => {
  it('hides strip when entity_360 is off', () => {
    expect(shouldShowEntity360Strip(false)).toBe(false)
    expect(shouldFetchEntity360(false)).toBe(false)
  })

  it('shows strip when entity_360 is on', () => {
    expect(shouldShowEntity360Strip(true)).toBe(true)
    expect(shouldFetchEntity360(true)).toBe(true)
  })

  it('formats hop captions with reference preferred', () => {
    expect(
      hopCaption({
        source_type: 'document',
        source_id: 3,
        title: 'Policy',
        reference: 'POL-3',
      }),
    ).toBe('POL-3')
  })

  it('detects neighbors', () => {
    expect(connectionsHasNeighbors(null)).toBe(false)
    expect(connectionsHasNeighbors({ upstream: [], downstream: [] })).toBe(false)
    expect(connectionsHasNeighbors({ upstream: [{ id: 1 }], downstream: [] })).toBe(true)
  })
})

describe('publishImpactPreviewFromBundle', () => {
  it('maps hops into checklist sections', () => {
    const preview = publishImpactPreviewFromBundle({
      complete: true,
      upstream: [
        {
          source_type: 'document',
          source_id: 2,
          title: 'Parent',
          reference: 'POL-2',
          relation: 'implements',
          direction: 'upstream',
          origin: 'graph',
        } as never,
      ],
      downstream: [],
      hops: [],
    })
    expect(preview.empty).toBe(false)
    expect(preview.sections.find((s) => s.id === 'dependents')?.items.length).toBe(1)
  })

  it('marks empty when no hops', () => {
    const preview = publishImpactPreviewFromBundle({
      complete: false,
      degraded_reasons: ['boom'],
      upstream: [],
      downstream: [],
      hops: [],
    })
    expect(preview.empty).toBe(true)
  })
})
