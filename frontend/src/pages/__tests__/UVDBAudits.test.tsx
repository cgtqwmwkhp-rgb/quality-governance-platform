import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

const mockGetDashboard = vi.fn()
const mockListSections = vi.fn()
const mockListAudits = vi.fn()
const mockGetIsoMapping = vi.fn()
const mockCreateAudit = vi.fn()
const mockCreateApiError = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  uvdbApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
    listSections: (...args: unknown[]) => mockListSections(...args),
    listAudits: (...args: unknown[]) => mockListAudits(...args),
    getISOMapping: (...args: unknown[]) => mockGetIsoMapping(...args),
    createAudit: (...args: unknown[]) => mockCreateAudit(...args),
  },
  ErrorClass: {
    NETWORK_ERROR: 'NETWORK_ERROR',
    SERVER_ERROR: 'SERVER_ERROR',
    AUTH_ERROR: 'AUTH_ERROR',
    NOT_FOUND: 'NOT_FOUND',
    UNKNOWN: 'UNKNOWN',
  },
  createApiError: (...args: unknown[]) => mockCreateApiError(...args),
  isSetupRequired: (payload: Record<string, unknown>) => payload?.error_class === 'SETUP_REQUIRED',
}))

vi.mock('../../components/ui/SetupRequiredPanel', () => ({
  SetupRequiredPanel: () => <div>setup required</div>,
}))

describe('UVDBAudits', () => {
  const renderPage = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>)

  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDashboard.mockResolvedValue({
      data: {
        summary: { total_audits: 3, active_audits: 1, completed_audits: 2, average_score: 91.2 },
        protocol: { name: 'UVDB Verify B2', version: 'V11.2', sections: 2 },
        certification_alignment: {},
      },
    })
    mockListSections.mockResolvedValue({
      data: {
        total_sections: 2,
        sections: [
          { number: '1', title: 'Management Systems', max_score: 10, question_count: 4, iso_mapping: {} },
          { number: '2', title: 'Information Security', max_score: 8, question_count: 3, iso_mapping: {} },
        ],
      },
    })
    mockListAudits.mockResolvedValue({
      data: {
        total: 1,
        audits: [
          {
            id: 5,
            audit_reference: 'UVDB-2026-0001',
            company_name: 'Plantexpand Limited',
            audit_type: 'B2',
            audit_date: '2026-03-20',
            status: 'completed',
            percentage_score: 92,
            lead_auditor: 'Jane Smith',
          },
        ],
      },
    })
    mockGetIsoMapping.mockResolvedValue({
      data: {
        description: 'ISO mapping',
        total_mappings: 1,
        mappings: [
          {
            uvdb_section: '2',
            uvdb_question: '2.3',
            uvdb_text: 'Information security controls',
            iso_9001: [],
            iso_14001: [],
            iso_45001: [],
            iso_27001: ['5.1', '8.1'],
          },
        ],
      },
    })
    mockCreateAudit.mockResolvedValue({
      data: {
        id: 8,
        audit_reference: 'UVDB-2026-0008',
        message: 'UVDB audit created',
      },
    })
    mockCreateApiError.mockReturnValue({ error_class: 'UNKNOWN' })
  })

  it('renders live UVDB data and shows ISO mappings from the backend contract', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default

    renderPage(<UVDBAudits />)

    expect(await screen.findByText('UVDB-2026-0001')).toBeInTheDocument()

    const mappingTab = screen
      .getAllByRole('button')
      .find((button) => button.textContent?.includes('uvdb.tab.iso_mapping'))
    expect(mappingTab).toBeTruthy()
    fireEvent.click(mappingTab!)

    expect(await screen.findByText('Information security controls')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockListAudits).toHaveBeenCalledWith({ skip: 0, limit: 50 })
    })
  })

  it('creates a new audit from the header action and refreshes the page data', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default

    renderPage(<UVDBAudits />)

    fireEvent.click(await screen.findByRole('button', { name: 'uvdb.new_audit' }))

    fireEvent.change(screen.getByLabelText('Company Name'), {
      target: { value: 'Plantexpand Limited' },
    })
    fireEvent.change(screen.getByLabelText('Lead Auditor'), {
      target: { value: 'Jane Smith' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Create Audit' }))

    await waitFor(() => {
      expect(mockCreateAudit).toHaveBeenCalledWith(
        expect.objectContaining({
          company_name: 'Plantexpand Limited',
          audit_type: 'B2',
          lead_auditor: 'Jane Smith',
        }),
      )
    })

    expect(await screen.findByText('Audit UVDB-2026-0008 created successfully.')).toBeInTheDocument()
    expect(mockListAudits).toHaveBeenCalledTimes(2)
  })

  it('retries the initial UVDB load only once after a transient failure', async () => {
    mockCreateApiError.mockReturnValue({ error_class: 'NETWORK_ERROR' })
    mockGetDashboard
      .mockRejectedValueOnce(new Error('temporary outage'))
      .mockResolvedValue({
        data: {
          summary: { total_audits: 3, active_audits: 1, completed_audits: 2, average_score: 91.2 },
          protocol: { name: 'UVDB Verify B2', version: 'V11.2', sections: 2 },
          certification_alignment: {},
        },
      })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByText('UVDB-2026-0001')).toBeInTheDocument()
    expect(mockGetDashboard).toHaveBeenCalledTimes(2)
    expect(mockListSections).toHaveBeenCalledTimes(2)
    expect(mockListAudits).toHaveBeenCalledTimes(2)
    expect(mockGetIsoMapping).toHaveBeenCalledTimes(2)
  })

  it('renders a zero-percent score instead of hiding it', async () => {
    mockListAudits.mockResolvedValueOnce({
      data: {
        total: 1,
        audits: [
          {
            id: 5,
            audit_reference: 'UVDB-2026-0001',
            company_name: 'Plantexpand Limited',
            audit_type: 'B2',
            audit_date: '2026-03-20',
            status: 'completed',
            percentage_score: 0,
            lead_auditor: 'Jane Smith',
          },
        ],
      },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findAllByText('0%')).not.toHaveLength(0)
  })
})
