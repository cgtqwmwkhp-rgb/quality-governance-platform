import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { PlanetMarkYearXlsxIngestPanel } from '../planetMarkYearXlsxIngestPanel'

const mockIngestMsXlsx = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, string>) => {
      if (opts?.year) return `${key}:${opts.year}`
      if (opts?.workbook) return `${key}:${opts.workbook}:${opts.year}`
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  planetMarkApi: {
    ingestMsXlsx: (...args: unknown[]) => mockIngestMsXlsx(...args),
  },
  getApiErrorMessage: (_err: unknown, fallback = 'failed') => fallback,
}))

describe('PlanetMarkYearXlsxIngestPanel PM-W1b', () => {
  beforeEach(() => {
    mockIngestMsXlsx.mockReset()
  })

  it('shows empty honesty state and enabled upload when no carbon', () => {
    render(
      <PlanetMarkYearXlsxIngestPanel
        yearId={1}
        yearLabel="YE2024"
        hasIngestedCarbon={false}
        currentTotal={null}
        currentPerFte={null}
        onIngested={vi.fn()}
      />,
    )
    expect(screen.getByTestId('planet-mark-years-xlsx-ingest')).toBeInTheDocument()
    expect(screen.getByText('planet_mark.shell.years.ingest_empty')).toBeInTheDocument()
    expect(screen.getByTestId('planet-mark-years-xlsx-ingest-button')).toBeEnabled()
  })

  it('uploads xlsx and shows ingested totals on success', async () => {
    const onIngested = vi.fn()
    mockIngestMsXlsx.mockResolvedValue({
      data: {
        year_id: 1,
        year_label: 'YE2024',
        scope_1: 477.4,
        scope_2_market: 2.0,
        scope_2_location: 10.9,
        scope_3: 175.0,
        total_emissions: 654.5,
        average_fte: 94.4,
        emissions_per_fte: 6.93,
        workbook_year_label: 'YE2024',
        source_filename: 'MS output - YE2024.xlsx',
        sources_upserted: 3,
        message: 'ok',
      },
    })

    render(
      <PlanetMarkYearXlsxIngestPanel
        yearId={1}
        yearLabel="YE2024"
        hasIngestedCarbon={false}
        currentTotal={null}
        currentPerFte={null}
        onIngested={onIngested}
      />,
    )

    const input = screen.getByTestId('planet-mark-years-xlsx-ingest-input')
    const file = new File(['xlsx-bytes'], 'MS output - YE2024.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(mockIngestMsXlsx).toHaveBeenCalled()
    })
    expect(await screen.findByTestId('planet-mark-years-xlsx-ingest-totals')).toBeInTheDocument()
    expect(screen.getByText('654.5')).toBeInTheDocument()
    expect(onIngested).toHaveBeenCalled()
  })

  it('blocks year-mismatched workbook client-side', async () => {
    render(
      <PlanetMarkYearXlsxIngestPanel
        yearId={1}
        yearLabel="YE2025"
        hasIngestedCarbon={false}
        currentTotal={null}
        currentPerFte={null}
        onIngested={vi.fn()}
      />,
    )
    const input = screen.getByTestId('planet-mark-years-xlsx-ingest-input')
    const file = new File(['xlsx-bytes'], 'MS output - YE2024.xlsx')
    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByTestId('planet-mark-years-xlsx-ingest-error')).toBeInTheDocument()
    expect(mockIngestMsXlsx).not.toHaveBeenCalled()
  })
})
