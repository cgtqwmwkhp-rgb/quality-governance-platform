import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockGetDashboard = vi.fn()
const mockListSections = vi.fn()
const mockListAudits = vi.fn()
const mockGetIsoMapping = vi.fn()

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
  },
  ErrorClass: {
    NETWORK_ERROR: 'NETWORK_ERROR',
    SERVER_ERROR: 'SERVER_ERROR',
    AUTH_ERROR: 'AUTH_ERROR',
    NOT_FOUND: 'NOT_FOUND',
    UNKNOWN: 'UNKNOWN',
  },
  createApiError: () => ({ error_class: 'UNKNOWN' }),
  isSetupRequired: (payload: Record<string, unknown>) => payload?.error_class === 'SETUP_REQUIRED',
}))

vi.mock('../../components/ui/SetupRequiredPanel', () => ({
  SetupRequiredPanel: () => <div>setup required</div>,
}))

describe('UVDBAudits', () => {
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
  })

  it('renders live UVDB data and shows ISO mappings from the backend contract', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default

    render(<UVDBAudits />)

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
})
