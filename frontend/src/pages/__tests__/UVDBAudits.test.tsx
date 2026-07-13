import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

const mockGetDashboard = vi.fn()
const mockListSections = vi.fn()
const mockListAudits = vi.fn()
const mockGetIsoMapping = vi.fn()
const mockGetAudit = vi.fn()
const mockCreateAudit = vi.fn()
const mockCreateApiError = vi.fn()
const mockGetReconciliation = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const mockApiGet = vi.fn()

vi.mock('../../api/client', () => ({
  default: {
    get: (...args: unknown[]) => mockApiGet(...args),
    defaults: { baseURL: '' },
  },
  uvdbApi: {
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
    listSections: (...args: unknown[]) => mockListSections(...args),
    listAudits: (...args: unknown[]) => mockListAudits(...args),
    getISOMapping: (...args: unknown[]) => mockGetIsoMapping(...args),
    getAudit: (...args: unknown[]) => mockGetAudit(...args),
    createAudit: (...args: unknown[]) => mockCreateAudit(...args),
  },
  externalAuditImportsApi: {
    getReconciliation: (...args: unknown[]) => mockGetReconciliation(...args),
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
          {
            number: '1',
            title: 'Management Systems',
            max_score: 10,
            question_count: 4,
            iso_mapping: {},
          },
          {
            number: '2',
            title: 'Information Security',
            max_score: 8,
            question_count: 3,
            iso_mapping: {},
          },
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
    mockGetAudit.mockResolvedValue({
      data: {
        id: 5,
        audit_reference: 'UVDB-2026-0001',
        company_name: 'Plantexpand Limited',
        audit_type: 'B2',
        audit_date: '2026-03-20',
        status: 'completed',
        lead_auditor: 'Jane Smith',
        total_score: 92,
        max_possible_score: 100,
        percentage_score: 92,
        section_scores: null,
        score_breakdown: [],
        source_document_asset_id: null,
        source_filename: null,
        findings_count: 0,
        major_findings: 0,
        minor_findings: 0,
        observations: 0,
        certifications: {},
        audit_notes: null,
      },
    })
    mockCreateApiError.mockReturnValue({ error_class: 'UNKNOWN' })
    mockApiGet.mockResolvedValue({ data: { sections: {} } })
    mockGetReconciliation.mockResolvedValue({
      data: {
        job_id: 72,
        audit_run_id: 41,
        audit_reference: 'UVDB-2026-0002',
        job_status: 'completed',
        canonical_read_model: 'specialist_sync_verification',
        specialist_home: { path: '/uvdb', label: 'Achilles / UVDB' },
        accepted_total: 1,
        promoted_total: 1,
        accepted_pending_total: 0,
        failed_total: 0,
        failed_drafts: [],
        materialized: {
          audit_findings: 1,
          capa_actions: 1,
          enterprise_risks: 1,
          uvdb_audit_id: 6,
        },
        proof_matrix: [],
        draft_results: [],
        view_links: {
          actions: '/actions?sourceType=audit_finding',
          risk_register: '/risk-register?auditOnly=1&auditRef=UVDB-2026-0002',
        },
      },
    })
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

    expect(
      await screen.findByText('Audit UVDB-2026-0008 created successfully.'),
    ).toBeInTheDocument()
    expect(mockListAudits).toHaveBeenCalledTimes(2)
  })

  it('retries the initial UVDB load only once after a transient failure', async () => {
    mockCreateApiError.mockReturnValue({ error_class: 'NETWORK_ERROR' })
    mockGetDashboard.mockRejectedValueOnce(new Error('temporary outage')).mockResolvedValue({
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

  it('presents protocol, scores, history and ISO mappings as clear specialist sections', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(
      await screen.findByRole('heading', { name: 'Scores and audit health' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'uvdb.tab.scores' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'uvdb.tab.protocol' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'uvdb.tab.audit_history' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'uvdb.tab.iso_mapping' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'uvdb.export_protocol' })).toBeDisabled()
  })

  it('links to import review only when a real audit run id is available', async () => {
    mockListAudits.mockResolvedValueOnce({
      data: {
        total: 2,
        audits: [
          {
            id: 6,
            audit_reference: 'UVDB-2026-0002',
            company_name: 'Plantexpand Limited',
            audit_type: 'B2',
            audit_date: '2026-04-20',
            status: 'completed',
            percentage_score: 89,
            lead_auditor: 'Alex Jones',
            audit_run_id: 41,
            import_job_id: 72,
          },
          {
            id: 5,
            audit_reference: 'UVDB-2026-0001',
            company_name: 'Plantexpand Limited',
            audit_type: 'B2',
            audit_date: '2026-03-20',
            status: 'completed',
            percentage_score: 92,
            lead_auditor: 'Jane Smith',
            audit_run_id: null,
            import_job_id: 71,
          },
        ],
      },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    fireEvent.click(await screen.findByRole('button', { name: 'uvdb.tab.audit_history' }))

    const links = screen.getAllByRole('link', { name: 'Import review' })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/audits/41/import-review?jobId=72')
  })

  it('exposes CAPA and Risk deep-links on the specialist home', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByText('UVDB-2026-0001')).toBeInTheDocument()
    const capaLinks = screen.getAllByTestId('uvdb-open-capa')
    expect(capaLinks[0]).toHaveAttribute('href', '/actions?sourceType=audit_finding')
    const riskLinks = screen.getAllByTestId('uvdb-open-risk')
    expect(riskLinks[0]).toHaveAttribute(
      'href',
      '/risk-register?auditOnly=1&auditRef=UVDB-2026-0001',
    )
  })

  it('shows recovery CTAs when auditRef misses the synced UVDB row', async () => {
    mockListAudits.mockResolvedValue({
      data: { total: 0, audits: [] },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    render(
      <MemoryRouter initialEntries={['/uvdb?auditRef=MISSING-REF']}>
        <UVDBAudits />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('uvdb-auditref-miss')).toBeInTheDocument()
    expect(screen.getByTestId('uvdb-auditref-miss-recovery-audits')).toHaveAttribute(
      'href',
      '/audits?source=achilles',
    )
    expect(screen.getByTestId('uvdb-auditref-miss-recovery-clear')).toHaveAttribute('href', '/uvdb')
    expect(screen.getByTestId('uvdb-auditref-miss-recovery-capa')).toHaveAttribute(
      'href',
      '/actions?sourceType=audit_finding',
    )
  })

  it('loads reconciliation proof when an import job id is present', async () => {
    mockListAudits.mockResolvedValueOnce({
      data: {
        total: 1,
        audits: [
          {
            id: 6,
            audit_reference: 'UVDB-2026-0002',
            company_name: 'Plantexpand Limited',
            audit_type: 'B2',
            audit_date: '2026-04-20',
            status: 'completed',
            percentage_score: 89,
            lead_auditor: 'Alex Jones',
            audit_run_id: 41,
            import_job_id: 72,
          },
        ],
      },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByTestId('uvdb-reconciliation-panel')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockGetReconciliation).toHaveBeenCalledWith(72)
    })
    expect(await screen.findByText(/Proof ready/i)).toBeInTheDocument()
  })

  it('shows useful empty states for scores, protocol, audit history and ISO mappings', async () => {
    mockGetDashboard.mockResolvedValueOnce({
      data: {
        summary: { total_audits: 0, active_audits: 0, completed_audits: 0, average_score: 0 },
        protocol: { name: 'UVDB Verify B2', version: 'V11.2', sections: 0 },
        certification_alignment: {},
      },
    })
    mockListSections.mockResolvedValueOnce({ data: { total_sections: 0, sections: [] } })
    mockListAudits.mockResolvedValueOnce({ data: { total: 0, audits: [] } })
    mockGetIsoMapping.mockResolvedValueOnce({
      data: { description: 'ISO mapping', total_mappings: 0, mappings: [] },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByText('No audit history yet')).toBeInTheDocument()
    expect(screen.getByText('Not scored')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'uvdb.tab.protocol' }))
    expect(screen.getByText('Protocol sections unavailable')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'uvdb.tab.audit_history' }))
    expect(screen.getByText('No audits yet')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'uvdb.tab.iso_mapping' }))
    expect(screen.getByText('No ISO cross-mapping data is available yet.')).toBeInTheDocument()
  })

  it('shows a retryable error state when UVDB data cannot be loaded', async () => {
    mockCreateApiError.mockReturnValue({ error_class: 'AUTH_ERROR' })
    mockGetDashboard.mockRejectedValueOnce(new Error('unauthorized'))

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByText('uvdb.failed_to_load')).toBeInTheDocument()
    expect(screen.getByText('uvdb.error_auth')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'uvdb.try_again' })).toBeInTheDocument()
  })
})
