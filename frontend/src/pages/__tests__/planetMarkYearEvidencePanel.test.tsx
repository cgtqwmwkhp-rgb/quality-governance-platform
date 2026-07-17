import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { PlanetMarkYearEvidencePanel } from '../planetMarkYearEvidencePanel'

const mockListEvidence = vi.fn()
const mockUploadEvidence = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { year?: string }) => {
      if (key === 'planet_mark.shell.years.evidence.hint' && opts?.year) {
        return `Evidence hint for ${opts.year}`
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  planetMarkApi: {
    listEvidence: (...args: unknown[]) => mockListEvidence(...args),
    uploadEvidence: (...args: unknown[]) => mockUploadEvidence(...args),
  },
  getApiErrorMessage: (_err: unknown, fallback = 'failed') => fallback,
}))

describe('PlanetMarkYearEvidencePanel', () => {
  beforeEach(() => {
    mockListEvidence.mockReset()
    mockUploadEvidence.mockReset()
    mockListEvidence.mockResolvedValue({ data: { total: 0, evidence: [] } })
  })

  it('shows honest empty state when no evidence is uploaded', async () => {
    render(<PlanetMarkYearEvidencePanel yearId={7} yearLabel="YE2024" />)

    expect(await screen.findByTestId('planet-mark-years-evidence-panel')).toBeInTheDocument()
    expect(screen.getByText('planet_mark.shell.years.evidence.title')).toBeInTheDocument()
    expect(screen.getByText('Evidence hint for YE2024')).toBeInTheDocument()
    expect(await screen.findByTestId('planet-mark-years-evidence-list-empty')).toBeInTheDocument()
    expect(mockListEvidence).toHaveBeenCalledWith(7)
  })

  it('lists uploaded measurement report and certificate rows', async () => {
    mockListEvidence.mockResolvedValue({
      data: {
        total: 2,
        evidence: [
          {
            id: 11,
            document_name: 'Plantexpand_Planet Mark_Measurement Report - YE2024.pdf',
            document_type: 'measurement_report',
            evidence_category: 'certification',
            period_covered: null,
            file_size_kb: 820,
            mime_type: 'application/pdf',
            is_verified: false,
            verified_by: null,
            linked_action_id: null,
            notes: null,
            uploaded_by: 'ops',
            uploaded_at: '2026-03-01T09:00:00Z',
            storage_key: 'k1',
          },
          {
            id: 12,
            document_name: 'Plantexpand_Planet Mark Certificate - YE2024.pdf',
            document_type: 'planet_mark_certificate',
            evidence_category: 'certification',
            period_covered: null,
            file_size_kb: 120,
            mime_type: 'application/pdf',
            is_verified: false,
            verified_by: null,
            linked_action_id: null,
            notes: null,
            uploaded_by: 'ops',
            uploaded_at: '2026-03-01T09:05:00Z',
            storage_key: 'k2',
          },
          {
            id: 13,
            document_name: 'utility.pdf',
            document_type: 'utility_bill',
            evidence_category: 'scope_2',
            period_covered: null,
            file_size_kb: 50,
            mime_type: 'application/pdf',
            is_verified: false,
            verified_by: null,
            linked_action_id: null,
            notes: null,
            uploaded_by: 'ops',
            uploaded_at: '2026-03-01T09:10:00Z',
            storage_key: 'k3',
          },
        ],
      },
    })

    render(<PlanetMarkYearEvidencePanel yearId={7} yearLabel="YE2024" />)

    expect(await screen.findByTestId('planet-mark-years-evidence-row-11')).toBeInTheDocument()
    expect(screen.getByTestId('planet-mark-years-evidence-row-12')).toBeInTheDocument()
    expect(screen.queryByTestId('planet-mark-years-evidence-row-13')).not.toBeInTheDocument()
    expect(screen.getByTestId('planet-mark-years-evidence-size-11')).toHaveTextContent('820 KB')
  })

  it('shows inline retry on 503 list failure without toast spam', async () => {
    mockListEvidence.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 503, data: { detail: 'Service unavailable' } },
      message: 'Request failed with status code 503',
    })
    mockListEvidence.mockResolvedValueOnce({ data: { total: 0, evidence: [] } })

    render(<PlanetMarkYearEvidencePanel yearId={7} yearLabel="YE2024" />)

    const errorPanel = await screen.findByTestId('planet-mark-years-evidence-list-error')
    expect(errorPanel).toBeInTheDocument()
    expect(within(errorPanel).getByTestId('planet-mark-years-evidence-list-retry')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('planet-mark-years-evidence-list-retry'))

    await waitFor(() => {
      expect(mockListEvidence).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByTestId('planet-mark-years-evidence-list-empty')).toBeInTheDocument()
  })

  it('shows inline retry on upload timeout', async () => {
    mockUploadEvidence.mockRejectedValueOnce({
      code: 'ECONNABORTED',
      message: 'timeout of 120000ms exceeded',
    })

    render(<PlanetMarkYearEvidencePanel yearId={7} yearLabel="YE2024" />)
    await screen.findByTestId('planet-mark-years-evidence-list-empty')

    const input = screen.getByTestId(
      'planet-mark-years-evidence-upload-measurement-report-input',
    ) as HTMLInputElement
    const file = new File(['pdf'], 'report.pdf', { type: 'application/pdf' })
    fireEvent.change(input, { target: { files: [file] } })

    const error = await screen.findByTestId(
      'planet-mark-years-evidence-upload-measurement-report-error',
    )
    expect(within(error).getByTestId('planet-mark-years-evidence-upload-measurement-report-retry'))
      .toBeInTheDocument()
  })
})
