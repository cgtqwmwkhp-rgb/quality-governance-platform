import { describe, expect, it } from 'vitest'
import {
  buildMsXlsxIngestFormData,
  formatIngestedTotals,
  inferYearLabelFromFilename,
  isRetryableMsXlsxIngestError,
  validateMsXlsxFile,
  yearLabelMatchesWorkbook,
} from '../planetMarkYearXlsxIngestHelpers'

describe('planetMarkYearXlsxIngestHelpers PM-W1b', () => {
  it('validates xlsx extension and size', () => {
    expect(validateMsXlsxFile(new File(['a'], 'report.pdf'))).toMatch(/xlsx/i)
    const big = new File([new Uint8Array(11 * 1024 * 1024)], 'YE2024.xlsx')
    expect(validateMsXlsxFile(big)).toMatch(/MB/)
    expect(validateMsXlsxFile(new File(['ok'], 'YE2024.xlsx'))).toBeNull()
  })

  it('infers and matches workbook year labels from Member Copy filenames', () => {
    expect(
      inferYearLabelFromFilename(
        'Plantexpand_Planet Mark_MS output - YE2024 - Member Copy.xlsx',
      ),
    ).toBe('YE2024')
    expect(yearLabelMatchesWorkbook('YE2024', 'MS output - YE2024.xlsx').ok).toBe(true)
    expect(yearLabelMatchesWorkbook('YE2025', 'MS output - YE2024.xlsx').ok).toBe(false)
    expect(yearLabelMatchesWorkbook('YE2024', 'totals.xlsx').ok).toBe(true)
  })

  it('builds multipart form data and formats ingested totals', () => {
    const file = new File(['x'], 'YE2024.xlsx')
    const fd = buildMsXlsxIngestFormData(file)
    expect(fd.get('file')).toBe(file)
    const formatted = formatIngestedTotals({
      year_id: 1,
      year_label: 'YE2024',
      scope_1: 477.439,
      scope_2_market: 2.049,
      scope_2_location: 10.876,
      scope_3: 174.971,
      total_emissions: 654.459,
      average_fte: 94.375,
      emissions_per_fte: 6.93465,
      workbook_year_label: 'YE2024',
      source_filename: 'YE2024.xlsx',
      sources_upserted: 3,
      message: 'ok',
    })
    expect(formatted.total).toBe('654.5')
    expect(formatted.perFte).toBe('6.93')
  })

  it('marks 503/timeout as retryable', () => {
    expect(isRetryableMsXlsxIngestError({ response: { status: 503 } })).toBe(true)
    expect(isRetryableMsXlsxIngestError({ code: 'ECONNABORTED' })).toBe(true)
    expect(isRetryableMsXlsxIngestError({ response: { status: 400 } })).toBe(false)
  })
})
