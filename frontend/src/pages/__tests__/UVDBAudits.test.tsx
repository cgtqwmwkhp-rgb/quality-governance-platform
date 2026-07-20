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
const mockDownloadProtocolPack = vi.fn()
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
    downloadProtocolPack: (...args: unknown[]) => mockDownloadProtocolPack(...args),
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
  const mockContentCoverage = {
    protocol_version: '11.8-target',
    status: 'partial' as const,
    total_sections: 15,
    loaded_sections: ['1', '2', '12', '13', '14', '15'],
    pending_sections: ['3', '4', '5', '6', '7', '8', '9', '10', '11'],
    loaded_question_count: 25,
    pending_question_count: 0,
    pending_reason:
      'Sections 3-11 await UVDB-QS-003 v11.8 protocol PDF ingest; section titles marked provisional where not PDF-pinned.',
  }

  const mockSections = [
    {
      number: '1',
      title: 'System Assurance and Compliance',
      max_score: 21,
      question_count: 5,
      iso_mapping: {},
      content_status: 'loaded' as const,
      title_provisional: false,
    },
    {
      number: '2',
      title: 'Quality Control and Assurance',
      max_score: 21,
      question_count: 5,
      iso_mapping: {},
      content_status: 'loaded' as const,
      title_provisional: false,
    },
    {
      number: '3',
      title: 'Health and Safety Policy and Leadership',
      max_score: 0,
      question_count: 0,
      iso_mapping: { '45001': 'pending' },
      content_status: 'pending_protocol_pdf' as const,
      title_provisional: true,
    },
    ...Array.from({ length: 8 }, (_, index) => {
      const number = String(index + 4)
      return {
        number,
        title: `Section ${number} shell`,
        max_score: 0,
        question_count: 0,
        iso_mapping: {},
        content_status: 'pending_protocol_pdf' as const,
        title_provisional: true,
      }
    }),
    {
      number: '12',
      title: 'Selection and Management of Sub-contractors',
      max_score: 12,
      question_count: 2,
      iso_mapping: {},
      content_status: 'loaded' as const,
      title_provisional: false,
    },
    {
      number: '13',
      title: 'Sourcing of Goods and Products',
      max_score: 12,
      question_count: 4,
      iso_mapping: {},
      content_status: 'loaded' as const,
      title_provisional: false,
    },
    {
      number: '14',
      title: 'Use of Work Equipment, Vehicles and Machines',
      max_score: 6,
      question_count: 1,
      iso_mapping: {},
      content_status: 'loaded' as const,
      title_provisional: false,
    },
    {
      number: '15',
      title: 'Key Performance Indicators',
      max_score: 0,
      question_count: 14,
      iso_mapping: {},
      content_status: 'loaded' as const,
      title_provisional: false,
    },
  ]

  const renderPage = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>)

  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDashboard.mockResolvedValue({
      data: {
        summary: { total_audits: 3, active_audits: 1, completed_audits: 2, average_score: 91.2 },
        protocol: {
          name: 'UVDB Verify B2',
          version: '11.8-target',
          sections: 15,
          content_coverage: mockContentCoverage,
        },
        certification_alignment: {},
        content_coverage: mockContentCoverage,
      },
    })
    mockListSections.mockResolvedValue({
      data: {
        total_sections: 15,
        content_coverage: mockContentCoverage,
        sections: mockSections,
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

    const mappingTab = screen.getByRole('tab', { name: /uvdb.shell.section.mapping/i })
    fireEvent.click(mappingTab)

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
        protocol: {
          name: 'UVDB Verify B2',
          version: '11.8-target',
          sections: 15,
          content_coverage: mockContentCoverage,
        },
        certification_alignment: {},
        content_coverage: mockContentCoverage,
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

  it('presents scores, protocol, history, mapping and export as Planet Mark-style sections', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(
      await screen.findByRole('heading', { name: 'Scores and audit health' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /uvdb.shell.section.scores/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: /uvdb.shell.section.protocol/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /uvdb.shell.section.audits/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /uvdb.shell.section.mapping/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /uvdb.shell.section.export/i })).toBeInTheDocument()
    expect(screen.getByTestId('uvdb-section-scores')).toBeInTheDocument()
    expect(screen.getByTestId('uvdb-protocol-partial-honesty')).toBeInTheDocument()
    expect(screen.getByText('uvdb.protocol_version_target')).toBeInTheDocument()
  })

  it('shows pending section honesty on the protocol tab', async () => {
    const UVDBAudits = (await import('../UVDBAudits')).default
    render(
      <MemoryRouter initialEntries={['/uvdb?section=protocol']}>
        <UVDBAudits />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('uvdb-section-3-pending')).toBeInTheDocument()
    expect(screen.getAllByText('uvdb.title_provisional').length).toBeGreaterThan(0)
    expect(screen.getAllByText('uvdb.questions_pending_pdf').length).toBeGreaterThan(0)
  })

  it('enables protocol export downloads on the export section', async () => {
    mockDownloadProtocolPack.mockResolvedValue({ data: new Blob(['{}']) })
    const UVDBAudits = (await import('../UVDBAudits')).default
    render(
      <MemoryRouter initialEntries={['/uvdb?section=export']}>
        <UVDBAudits />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('uvdb-section-export')).toBeInTheDocument()
    expect(screen.getByTestId('uvdb-export-protocol-honesty')).toHaveTextContent(
      'uvdb.shell.export_honesty',
    )
    expect(screen.getByTestId('uvdb-export-protocol-json')).toBeEnabled()
    expect(screen.getByTestId('uvdb-export-protocol-xlsx')).toBeEnabled()

    fireEvent.click(screen.getByTestId('uvdb-export-protocol-json'))
    await waitFor(() => {
      expect(mockDownloadProtocolPack).toHaveBeenCalledWith('json')
    })

    fireEvent.click(screen.getByTestId('uvdb-export-protocol-xlsx'))
    await waitFor(() => {
      expect(mockDownloadProtocolPack).toHaveBeenCalledWith('xlsx')
    })
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

    fireEvent.click(await screen.findByRole('tab', { name: /uvdb.shell.section.audits/i }))

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
      <MemoryRouter initialEntries={['/uvdb?auditRef=MISSING-REF&runId=41&jobId=72']}>
        <UVDBAudits />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('uvdb-auditref-miss')).toBeInTheDocument()
    expect(screen.getByTestId('uvdb-auditref-miss-recovery-import-review')).toHaveAttribute(
      'href',
      '/audits/41/import-review?jobId=72',
    )
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
    mockGetReconciliation.mockResolvedValueOnce({
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
        proof_matrix: [
          { step: 'promotion', status: 'ok', detail: '1 finding(s)' },
          { step: 'uvdb_sync', status: 'ok', detail: 'UVDB audit id 6' },
        ],
        draft_results: [{ finding_id: 501 }],
        view_links: {
          actions: '/actions?sourceType=audit_finding&sourceId=501',
          risk_register: '/risk-register?auditOnly=1&auditRef=UVDB-2026-0002',
          import_review: '/audits/41/import-review?jobId=72',
        },
      },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByTestId('uvdb-reconciliation-panel')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockGetReconciliation).toHaveBeenCalledWith(72)
    })
    expect(await screen.findByText(/Proof ready/i)).toBeInTheDocument()
    expect(screen.getByTestId('uvdb-proof-step-uvdb_sync')).toHaveTextContent('uvdb sync: ok')
    const capaLinks = screen.getAllByTestId('uvdb-open-capa')
    expect(
      capaLinks.some((link) =>
        link.getAttribute('href')?.includes('sourceId=501'),
      ),
    ).toBe(true)
    expect(screen.getAllByTestId('uvdb-open-import-review')[0]).toHaveAttribute(
      'href',
      '/audits/41/import-review?jobId=72',
    )
  })

  it('labels partial reconciliation honestly when drafts remain pending', async () => {
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
    mockGetReconciliation.mockResolvedValueOnce({
      data: {
        job_id: 72,
        audit_run_id: 41,
        audit_reference: 'UVDB-2026-0002',
        job_status: 'review_required',
        canonical_read_model: 'specialist_sync_verification',
        specialist_home: { path: '/uvdb', label: 'Achilles / UVDB' },
        accepted_total: 2,
        promoted_total: 1,
        accepted_pending_total: 1,
        failed_total: 0,
        failed_drafts: [],
        materialized: {
          audit_findings: 1,
          capa_actions: 0,
          enterprise_risks: 0,
          uvdb_audit_id: 6,
        },
        proof_matrix: [{ step: 'uvdb_sync', status: 'ok', detail: 'Synced' }],
        draft_results: [],
        view_links: {},
      },
    })

    const UVDBAudits = (await import('../UVDBAudits')).default
    renderPage(<UVDBAudits />)

    expect(await screen.findByText(/partial/i)).toBeInTheDocument()
  })

  it('shows useful empty states for scores, protocol, audit history and ISO mappings', async () => {
    mockGetDashboard.mockResolvedValueOnce({
      data: {
        summary: { total_audits: 0, active_audits: 0, completed_audits: 0, average_score: 0 },
        protocol: {
          name: 'UVDB Verify B2',
          version: '11.8-target',
          sections: 0,
          content_coverage: {
            ...mockContentCoverage,
            status: 'partial',
            loaded_sections: [],
            pending_sections: [],
            total_sections: 0,
          },
        },
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

    fireEvent.click(screen.getByRole('tab', { name: /uvdb.shell.section.protocol/i }))
    expect(screen.getByText('Protocol sections unavailable')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /uvdb.shell.section.audits/i }))
    expect(screen.getByText('No audits yet')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /uvdb.shell.section.mapping/i }))
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
