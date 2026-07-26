import { describe, expect, it } from 'vitest'
import { buildCertShelfEmptyCopy } from '../assuranceCertShelfHelpers'

describe('assuranceCertShelfHelpers', () => {
  it('PX-243: unpopulated shelf copy is not a filter miss', () => {
    const copy = buildCertShelfEmptyCopy({ schemeFilter: 'all', statusFilter: 'all' })
    expect(copy.kind).toBe('unpopulated')
    expect(copy.description).toMatch(/not a filter result/i)
  })

  it('PX-243: active filters use a distinct empty message', () => {
    const copy = buildCertShelfEmptyCopy({
      schemeFilter: 'uvdb_achilles',
      statusFilter: 'valid',
    })
    expect(copy.kind).toBe('filtered')
    expect(copy.title).toMatch(/match these filters/i)
  })
})
