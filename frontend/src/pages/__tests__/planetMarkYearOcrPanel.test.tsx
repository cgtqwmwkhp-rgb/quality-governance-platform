import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { PlanetMarkYearOcrPanel } from '../planetMarkYearOcrPanel'

const mockExtract = vi.fn()
const mockApply = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { year?: string; file?: string; method?: string }) => {
      if (opts?.year) return `${key}:${opts.year}`
      if (opts?.file) return `${key}:${opts.file}`
      if (opts?.method) return `${key}:${opts.method}`
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  planetMarkApi: {
    extractYearOcr: (...args: unknown[]) => mockExtract(...args),
    applyYearOcr: (...args: unknown[]) => mockApply(...args),
  },
  getApiErrorMessage: (_err: unknown, fallback = 'failed') => fallback,
}))

const richPreview = {
  source_filename: 'YE2024-report.pdf',
  document_kind: 'measurement_report',
  extraction_method: 'pdfplumber',
  total_co2e_tonnes: { value: '654.459', confidence: 'high', raw_snippet: 'Total 654.459 tCO2e' },
  co2e_per_fte: { value: '6.935', confidence: 'high', raw_snippet: null },
  average_fte: { value: '94.375', confidence: 'high', raw_snippet: null },
  certificate_number: { value: 'PM-2024-1', confidence: 'high', raw_snippet: null },
  reporting_period_label: { value: 'YE2024', confidence: 'high', raw_snippet: null },
  certification_status_cue: { value: 'certified', confidence: 'high', raw_snippet: null },
  warnings: [],
  text_excerpt: '…',
  year_label: 'YE2024',
  xlsx_ingested: false,
  period_mismatch_warning: null,
  evidence_id: 11,
}

describe('PlanetMarkYearOcrPanel', () => {
  beforeEach(() => {
    mockExtract.mockReset()
    mockApply.mockReset()
  })

  it('shows honest empty state when no stored evidence', () => {
    render(
      <PlanetMarkYearOcrPanel
        yearId={7}
        yearLabel="YE2024"
        measurementReportEvidenceId={null}
        certificateEvidenceId={null}
        onApplied={vi.fn()}
      />,
    )
    expect(screen.getByTestId('planet-mark-years-ocr-empty')).toBeInTheDocument()
    expect(screen.getByTestId('planet-mark-years-ocr-scan')).toBeDisabled()
  })

  it('scan → preview → apply happy path', async () => {
    mockExtract.mockResolvedValue({ data: richPreview })
    mockApply.mockResolvedValue({
      data: {
        year_id: 7,
        year_label: 'YE2024',
        applied: [{ field: 'total_co2e_tonnes', action: 'apply', value: '654.459', reason: null }],
        skipped: [],
        message: 'Applied 1 field(s) from OCR preview',
        updated: {
          total_emissions: 654.459,
          average_fte: 94.375,
          emissions_per_fte: 6.935,
          certificate_number: 'PM-2024-1',
        },
      },
    })
    const onApplied = vi.fn()

    render(
      <PlanetMarkYearOcrPanel
        yearId={7}
        yearLabel="YE2024"
        measurementReportEvidenceId={11}
        certificateEvidenceId={null}
        onApplied={onApplied}
      />,
    )

    fireEvent.click(screen.getByTestId('planet-mark-years-ocr-scan'))

    expect(await screen.findByTestId('planet-mark-years-ocr-preview')).toBeInTheDocument()
    expect(screen.getByTestId('planet-mark-years-ocr-field-total_co2e_tonnes')).toHaveTextContent(
      '654.459',
    )

    fireEvent.click(screen.getByTestId('planet-mark-years-ocr-apply'))

    await waitFor(() => {
      expect(mockApply).toHaveBeenCalled()
      expect(onApplied).toHaveBeenCalled()
    })
    expect(await screen.findByTestId('planet-mark-years-ocr-apply-result')).toBeInTheDocument()
  })

  it('blocks apply over xlsx SSOT until force checkbox confirmed', async () => {
    mockExtract.mockResolvedValue({
      data: { ...richPreview, xlsx_ingested: true },
    })

    render(
      <PlanetMarkYearOcrPanel
        yearId={7}
        yearLabel="YE2024"
        measurementReportEvidenceId={11}
        certificateEvidenceId={null}
        onApplied={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTestId('planet-mark-years-ocr-scan'))
    expect(await screen.findByTestId('planet-mark-years-ocr-xlsx-ssot')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('planet-mark-years-ocr-apply'))
    expect(await screen.findByTestId('planet-mark-years-ocr-error')).toBeInTheDocument()
    expect(mockApply).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('planet-mark-years-ocr-force-overwrite'))
    fireEvent.click(screen.getByTestId('planet-mark-years-ocr-apply'))

    await waitFor(() => {
      expect(mockApply).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ force_overwrite_totals: true }),
      )
    })
  })
})
