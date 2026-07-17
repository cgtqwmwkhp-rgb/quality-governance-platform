import { describe, expect, it } from 'vitest'
import {
  evidenceHasStorageKey,
  latestEvidenceIdForType,
  PLANET_MARK_YEAR_CERT_DOC_TYPES,
} from '../planetMarkYearEvidenceHelpers'
import type { PlanetMarkEvidenceRecord } from '../../api/planetMarkClient'

function row(
  partial: Partial<PlanetMarkEvidenceRecord> & Pick<PlanetMarkEvidenceRecord, 'id' | 'document_type'>,
): PlanetMarkEvidenceRecord {
  return {
    document_name: 'doc.pdf',
    evidence_category: 'certification',
    period_covered: null,
    file_size_kb: 10,
    mime_type: 'application/pdf',
    is_verified: false,
    verified_by: null,
    linked_action_id: null,
    notes: null,
    uploaded_by: 'ops',
    uploaded_at: '2026-03-01T09:00:00Z',
    storage_key: null,
    ...partial,
  }
}

describe('planetMarkYearEvidenceHelpers storage honesty', () => {
  it('detects missing storage_key as not downloadable', () => {
    expect(evidenceHasStorageKey(null)).toBe(false)
    expect(evidenceHasStorageKey('')).toBe(false)
    expect(evidenceHasStorageKey('planet-mark/k1')).toBe(true)
  })

  it('latestEvidenceIdForType ignores phantom rows without storage', () => {
    const evidence = [
      row({
        id: 1,
        document_type: PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport,
        storage_key: null,
        uploaded_at: '2026-03-02T09:00:00Z',
      }),
      row({
        id: 2,
        document_type: PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport,
        storage_key: 'k2',
        uploaded_at: '2026-03-01T09:00:00Z',
      }),
      row({
        id: 3,
        document_type: PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate,
        storage_key: 'k3',
      }),
    ]
    expect(
      latestEvidenceIdForType(evidence, PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport),
    ).toBe(2)
    expect(latestEvidenceIdForType(evidence, PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate)).toBe(3)
  })
})
