import { describe, expect, it } from 'vitest'
import {
  investigationLinkedEvidenceParams,
  investigationNativeEvidenceParams,
  mergeEvidenceAssetsById,
} from '../investigationEvidenceQuery'

describe('investigationEvidenceQuery', () => {
  it('lists native investigation uploads by source_module, not the link column', () => {
    expect(investigationNativeEvidenceParams(12)).toEqual({
      source_module: 'investigation',
      source_id: 12,
      page: 1,
      page_size: 50,
    })
  })

  it('lists source-record files by linked_investigation_id without a source_module filter', () => {
    expect(investigationLinkedEvidenceParams(12)).toEqual({
      linked_investigation_id: 12,
      page: 1,
      page_size: 50,
    })
  })

  it('keeps both native and linked rows, and does not duplicate a row that appears in both', () => {
    const merged = mergeEvidenceAssetsById([
      [{ id: 2, title: 'incident photo' }],
      [{ id: 2, title: 'incident photo' }, { id: 9, title: 'investigation note' }],
    ])

    expect(merged.map((row) => row.id).sort((a, b) => a - b)).toEqual([2, 9])
  })
})
