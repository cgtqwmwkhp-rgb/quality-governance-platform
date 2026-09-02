import { describe, expect, it } from 'vitest'
import {
  auditQuestionEvidenceDescription,
  buildEvidenceResponseJson,
  extractEvidenceAssetIds,
  isSignatureDataUrl,
  mergeListedEvidenceIdsIntoMap,
  parseAuditQuestionIdFromEvidenceDescription,
  signatureUploadFilename,
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

  it('detects signature data URLs vs remote signed URLs', () => {
    expect(isSignatureDataUrl('data:image/png;base64,abc')).toBe(true)
    expect(isSignatureDataUrl('https://blob.example/sig.png')).toBe(false)
    expect(isSignatureDataUrl(undefined)).toBe(false)
  })

  it('builds a signature upload filename for the question', () => {
    expect(signatureUploadFilename(4)).toMatch(/^audit-signature-q4-\d+\.png$/)
  })

  it('parses audit_question:{id} from evidence descriptions', () => {
    expect(parseAuditQuestionIdFromEvidenceDescription('audit_question:151')).toBe('151')
    expect(parseAuditQuestionIdFromEvidenceDescription('photo, audit_question:88 extra')).toBe('88')
    expect(parseAuditQuestionIdFromEvidenceDescription('signature png')).toBe(null)
    expect(parseAuditQuestionIdFromEvidenceDescription(undefined)).toBe(null)
  })

  it('merges listed blobs onto questions that have no response rows', () => {
    const merged = mergeListedEvidenceIdsIntoMap(
      {},
      [
        { id: 501, description: 'audit_question:151' },
        { id: 502, description: 'audit_question:152' },
        { id: 503, description: 'audit_question:999' },
        { id: 0, description: 'audit_question:151' },
      ],
      new Set(['151', '152']),
    )
    expect(merged).toEqual({
      '151': [501],
      '152': [502],
    })
  })

  it('unions listed ids with existing response evidence ids', () => {
    const merged = mergeListedEvidenceIdsIntoMap(
      { '151': [10] },
      [{ id: 501, description: 'audit_question:151' }],
      new Set(['151']),
    )
    expect(merged['151']).toEqual([10, 501])
  })
})
