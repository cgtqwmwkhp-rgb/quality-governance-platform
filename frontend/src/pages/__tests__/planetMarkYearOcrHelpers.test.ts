import { describe, expect, it } from 'vitest'
import {
  canApplyOcrPreview,
  evidenceHasDownloadableStorage,
  formatOcrFieldDisplay,
  isExtractedField,
  needsXlsxOverwriteConfirmation,
  type PlanetMarkOcrExtractResponse,
} from '../planetMarkYearOcrHelpers'

function field(value: string | null, confidence = value ? 'high' : 'none') {
  return { value, confidence, raw_snippet: value }
}

function preview(
  overrides: Partial<PlanetMarkOcrExtractResponse> = {},
): PlanetMarkOcrExtractResponse {
  return {
    source_filename: 'report.pdf',
    document_kind: 'measurement_report',
    extraction_method: 'pdfplumber',
    total_co2e_tonnes: field(null),
    co2e_per_fte: field(null),
    average_fte: field(null),
    certificate_number: field(null),
    reporting_period_label: field(null),
    certification_status_cue: field(null),
    warnings: [],
    text_excerpt: '',
    year_label: 'YE2024',
    xlsx_ingested: false,
    period_mismatch_warning: null,
    evidence_id: 1,
    ...overrides,
  }
}

describe('planetMarkYearOcrHelpers', () => {
  it('treats none-confidence as not extracted', () => {
    expect(isExtractedField(field(null))).toBe(false)
    expect(isExtractedField(field('12.3', 'none'))).toBe(false)
    expect(isExtractedField(field('12.3', 'high'))).toBe(true)
    expect(formatOcrFieldDisplay(field(null))).toBe('—')
    expect(formatOcrFieldDisplay(field('12.3'))).toBe('12.3')
  })

  it('canApply requires at least one applyable field', () => {
    expect(canApplyOcrPreview(preview())).toBe(false)
    expect(
      canApplyOcrPreview(preview({ total_co2e_tonnes: field('100') })),
    ).toBe(true)
  })

  it('xlsx overwrite confirmation only when totals present and xlsx ingested', () => {
    expect(
      needsXlsxOverwriteConfirmation(
        preview({ xlsx_ingested: true, total_co2e_tonnes: field('100') }),
      ),
    ).toBe(true)
    expect(
      needsXlsxOverwriteConfirmation(
        preview({ xlsx_ingested: true, certificate_number: field('PM-1') }),
      ),
    ).toBe(false)
    expect(
      needsXlsxOverwriteConfirmation(
        preview({ xlsx_ingested: false, total_co2e_tonnes: field('100') }),
      ),
    ).toBe(false)
  })

  it('storage honesty helper', () => {
    expect(evidenceHasDownloadableStorage('planet-mark/k1')).toBe(true)
    expect(evidenceHasDownloadableStorage(null)).toBe(false)
    expect(evidenceHasDownloadableStorage('')).toBe(false)
  })
})
