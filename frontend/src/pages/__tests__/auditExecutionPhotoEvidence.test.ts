import { describe, expect, it } from 'vitest'
import {
  auditQuestionEvidenceDescription,
  buildEvidenceResponseJson,
  extractEvidenceAssetIds,
} from '../auditExecutionPhotoEvidence'

describe('auditExecutionPhotoEvidence', () => {
  it('builds and extracts evidence asset ids from response_json', () => {
    const json = buildEvidenceResponseJson([3, 3, 7, 0, -1])
    expect(json).toEqual({ evidence_asset_ids: [3, 7] })
    expect(extractEvidenceAssetIds(json)).toEqual([3, 7])
    expect(extractEvidenceAssetIds(null)).toEqual([])
    expect(extractEvidenceAssetIds({ evidence_asset_ids: ['12', 'x'] })).toEqual([12])
  })

  it('tags uploads with a stable question description', () => {
    expect(auditQuestionEvidenceDescription(9)).toBe('audit_question:9')
  })
})
