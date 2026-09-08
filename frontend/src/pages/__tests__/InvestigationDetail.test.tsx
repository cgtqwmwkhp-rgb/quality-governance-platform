import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import InvestigationDetail from '../InvestigationDetail'

const mockNavigate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: '7' }),
  }
})

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

vi.mock('../../utils/investigationStatusFilter', () => ({
  getStatusDisplay: () => ({
    label: 'In Progress',
    className: 'bg-primary/10 text-primary',
  }),
}))

vi.mock('../investigation/InvestigationHeader', () => ({
  default: ({
    investigation,
    sourceLink,
  }: {
    investigation: { title: string; reference_number: string }
    sourceLink?: { href: string; label: string } | null
  }) => (
    <div data-testid="investigation-identity-chrome">
      <p data-testid="investigation-role-eyebrow">investigations.identity.eyebrow</p>
      <span data-testid="investigation-primary-ref">{investigation.reference_number}</span>
      <h1>{investigation.title}</h1>
      <p data-testid="investigation-purpose">investigations.identity.purpose</p>
      {sourceLink ? (
        <span data-testid="investigation-source-chip">
          Source: {sourceLink.label} #{investigation.reference_number}
        </span>
      ) : null}
    </div>
  ),
}))

vi.mock('../investigation/InvestigationTimeline', () => ({
  default: ({
    timelineFilter,
    onTimelineFilterChange,
  }: {
    timelineFilter: string
    onTimelineFilterChange: (value: string) => void
  }) => (
    <div data-testid="investigation-timeline-panel">
      <span data-testid="investigation-timeline-current-filter">{timelineFilter}</span>
      <div data-testid="investigation-activity-spine">activity spine</div>
      <button
        type="button"
        data-testid="investigation-timeline-set-status"
        onClick={() => onTimelineFilterChange('STATUS_CHANGED')}
      >
        Filter status
      </button>
    </div>
  ),
}))

vi.mock('../investigation/InvestigationComments', () => ({
  default: () => <div>Comments</div>,
}))

vi.mock('../investigation/InvestigationActions', () => ({
  default: () => <div data-testid="investigation-actions-panel">Actions panel</div>,
}))

vi.mock('../investigation/InvestigationEvidence', () => ({
  default: () => <div>Evidence</div>,
}))

vi.mock('../investigation/investigationReportHelpers', () => ({
  buildGeneratedPackDownload: vi.fn(),
  buildPackManifestStubDownload: vi.fn(() => ({
    filename: 'stub.json',
    body: '{}',
    exportKind: 'manifest_stub',
  })),
  packPdfFilename: vi.fn(() => 'investigation-report-INV-7-abcdef12.pdf'),
  triggerPackDownload: vi.fn(),
  triggerPackPdfDownload: vi.fn(),
}))

vi.mock('../investigation/investigationDetailApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../investigation/investigationDetailApi')>()),
  fetchCustomerPackPdf: vi.fn(),
}))

vi.mock('../../components/EngineerPeoplePicker', () => ({
  EngineerPeoplePicker: ({
    valueLabel,
    onChange,
    testId,
  }: {
    valueLabel?: string
    onChange?: (next: { label: string; user?: { id: number; email: string }; hasLogin: boolean } | null) => void
    testId?: string
  }) => (
    <div>
      <input
        data-testid={testId || 'mock-engineer-people-picker'}
        value={valueLabel || ''}
        onChange={(event) =>
          onChange?.({ label: event.target.value, hasLogin: false })
        }
      />
      <button
        type="button"
        data-testid={`${testId || 'mock-engineer-people-picker'}-pick`}
        onClick={() =>
          onChange?.({
            label: 'Roster Engineer',
            user: { id: 4, email: 'david@example.com' },
            hasLogin: true,
          })
        }
      >
        Pick engineer
      </button>
    </div>
  ),
}))

vi.mock('../../api/client', () => ({
  investigationsApi: {
    get: vi.fn(),
    getTimeline: vi.fn(),
    getComments: vi.fn(),
    getPacks: vi.fn(),
    getClosureValidation: vi.fn(),
    generatePack: vi.fn(),
    update: vi.fn(),
    addComment: vi.fn(),
    autosave: vi.fn(),
    createCapa: vi.fn(),
    // INV-C7: findings are rows behind their own endpoints.
    listFindings: vi.fn(),
    createFinding: vi.fn(),
    updateFinding: vi.fn(),
    deleteFinding: vi.fn(),
    reorderFindings: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
    update: vi.fn(),
  },
  evidenceAssetsApi: {
    list: vi.fn(),
    upload: vi.fn(),
    delete: vi.fn(),
  },
  workforceApi: {
    listEngineers: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  checkPackCapability: vi.fn(),
  getApiErrorMessage: (err: Error) => err.message,
}))

const mockInvestigation = {
  id: 7,
  reference_number: 'INV-7',
  template_id: 1,
  assigned_entity_type: 'road_traffic_collision',
  assigned_entity_id: 42,
  title: 'Collision investigation',
  description: 'Determine the root cause',
  status: 'in_progress',
  data: {},
  created_at: '2026-03-01T10:00:00Z',
  updated_at: '2026-03-02T10:00:00Z',
}

/** INV-C7: build a findings list response the way the API returns it. */
function findingsResponse(bodies: string[], startId = 1) {
  const items = bodies.map((body, index) => ({
    id: startId + index,
    investigation_id: 7,
    body,
    sort_order: index,
    created_by_id: null,
    created_at: '2026-03-02T10:00:00Z',
    updated_at: '2026-03-02T10:00:00Z',
  }))
  return {
    data: {
      items,
      total: items.length,
      investigation_id: 7,
      findings_text: items.map((item, index) => `${index + 1}. ${item.body}`).join('\n'),
    },
  }
}

function renderPage() {
  return render(
    <BrowserRouter>
      <InvestigationDetail />
    </BrowserRouter>,
  )
}

describe('InvestigationDetail', () => {
  let client: Awaited<typeof import('../../api/client')>

  beforeEach(async () => {
    vi.clearAllMocks()
    mockNavigate.mockReset()
    client = await import('../../api/client')

    client.investigationsApi.get.mockResolvedValue({ data: mockInvestigation })
    client.investigationsApi.getTimeline.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 50, pages: 1, investigation_id: 7 },
    })
    client.investigationsApi.getComments.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 50, pages: 1, investigation_id: 7 },
    })
    client.investigationsApi.getPacks.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            investigation_id: 7,
            generated_at: '2026-03-05T10:00:00Z',
            pack_uuid: 'abcdef1234567890',
            audience: 'customer',
            checksum_sha256: '1234567890abcdef1234567890abcdef',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
        investigation_id: 7,
      },
    })
    client.investigationsApi.getClosureValidation.mockResolvedValue({
      data: { can_close: false, reasons: ['STATUS_NOT_COMPLETE'] },
    })
    client.investigationsApi.listFindings.mockResolvedValue(findingsResponse([]))
    client.actionsApi.list.mockResolvedValue({ data: { items: [] } })
    client.evidenceAssetsApi.list.mockResolvedValue({ data: { items: [] } })
    client.checkPackCapability.mockResolvedValue({ canGenerate: true })
  })

  it('downloads a manifest stub when Report history download is clicked', async () => {
    const helpers = await import('../investigation/investigationReportHelpers')

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    await waitFor(() => {
      expect(screen.getByTestId('investigation-pack-download-1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('investigation-pack-download-1'))

    await waitFor(() => {
      expect(helpers.triggerPackDownload).toHaveBeenCalled()
    })

    const { toast } = await import('../../contexts/ToastContext')
    expect(toast.success).toHaveBeenCalledWith(
      'Manifest stub downloaded — use PDF for the issuable document.',
    )
  })

  // PX-143: the customer deliverable is a PDF, not a JSON payload.
  it('downloads a real PDF for a stored pack from Report history', async () => {
    const detailApi = await import('../investigation/investigationDetailApi')
    const helpers = await import('../investigation/investigationReportHelpers')
    const pdfBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    vi.mocked(detailApi.fetchCustomerPackPdf).mockResolvedValue(pdfBlob)

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    const pdfButton = await screen.findByTestId('investigation-pack-download-pdf-1')
    fireEvent.click(pdfButton)

    await waitFor(() => {
      expect(detailApi.fetchCustomerPackPdf).toHaveBeenCalledWith(7, 1)
    })
    expect(helpers.triggerPackPdfDownload).toHaveBeenCalledWith(
      pdfBlob,
      'investigation-report-INV-7-abcdef12.pdf',
    )
  })

  it('surfaces a PDF build failure instead of downloading an empty file', async () => {
    const detailApi = await import('../investigation/investigationDetailApi')
    const helpers = await import('../investigation/investigationReportHelpers')
    vi.mocked(detailApi.fetchCustomerPackPdf).mockRejectedValue(new Error('PDF export unavailable'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    fireEvent.click(await screen.findByTestId('investigation-pack-download-pdf-1'))

    const { toast } = await import('../../contexts/ToastContext')
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('PDF export unavailable')
    })
    expect(helpers.triggerPackPdfDownload).not.toHaveBeenCalled()
  })

  // PX-144: the omit rule must not be stated as a raw permission constant.
  it('states the omit approval requirement in plain language', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    const scope = await screen.findByTestId('investigation-hsg245-report-sections')
    expect(scope).not.toHaveTextContent('investigation:approve_customer_omit')
    expect(scope).toHaveTextContent('Approve leaving a section out of the customer pack')
  })

  it('renders generated pack checksums from the aligned API contract', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    await waitFor(() => {
      expect(screen.getByText(/UUID: abcdef12/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/SHA256: 1234567890ab/i)).toBeInTheDocument()
    expect(client.investigationsApi.getPacks).toHaveBeenCalledWith(7, { page: 1, page_size: 50 })
  })

  it('links back to the source record and opens in-context CAPA create when empty', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(
      screen.getAllByRole('button', { name: 'investigations.handoff.open_source_report' })[0],
    )
    expect(mockNavigate).toHaveBeenCalledWith('/rtas/42')

    fireEvent.click(screen.getByTestId('investigation-capa-handoff-cta'))
    expect(mockNavigate).not.toHaveBeenCalledWith(
      expect.stringContaining('/actions?sourceType=investigation'),
    )
    expect(screen.getByTestId('investigation-actions-panel')).toBeInTheDocument()
  })

  it('shows Investigation workspace identity chrome (C1)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-identity-chrome')).toBeInTheDocument()
    })

    expect(screen.getByTestId('investigation-role-eyebrow')).toHaveTextContent(
      'investigations.identity.eyebrow',
    )
    expect(screen.getByTestId('investigation-primary-ref')).toHaveTextContent('INV-7')
    expect(screen.getByTestId('investigation-purpose')).toHaveTextContent(
      'investigations.identity.purpose',
    )
  })

  it('surfaces Summary status/level/assignee and editable findings (C2)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-meta-controls')).toBeInTheDocument()
    })

    expect(screen.getByTestId('investigation-status-select')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-level-display')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-assignee-input')).toBeInTheDocument()
    // INV-C7: the single findings textarea is now a list editor.
    expect(screen.getByTestId('investigation-findings-list')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-notes-section')).toBeInTheDocument()
  })

  it('applies honest Timeline filter enums to the timeline API (C2)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Timeline' }))

    await waitFor(() => {
      expect(screen.getByTestId('investigation-timeline-panel')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('investigation-timeline-set-status'))

    await waitFor(() => {
      expect(client.investigationsApi.getTimeline).toHaveBeenCalledWith(7, {
        page: 1,
        page_size: 50,
        type: 'STATUS_CHANGED',
      })
    })
  })

  it('shows Internal/External Report buttons and permission honesty (C3)', async () => {
    client.checkPackCapability.mockResolvedValue({
      canGenerate: false,
      reason: 'You do not have permission to generate packs',
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    await waitFor(() => {
      expect(screen.getByTestId('investigation-report-internal')).toBeInTheDocument()
    })

    expect(screen.getByTestId('investigation-report-external')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-report-gated')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-report-internal')).toBeDisabled()
    expect(screen.getByTestId('investigation-report-external')).toBeDisabled()
  })

  it('navigates to Actions list when CAPA already exists (open mode)', async () => {
    client.actionsApi.list.mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            title: 'Install barrier',
            status: 'open',
            source_type: 'investigation',
            source_id: 7,
          },
        ],
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-capa-handoff-cta')).toHaveTextContent(
        'investigations.handoff.open_capa',
      )
    })

    fireEvent.click(screen.getByTestId('investigation-capa-handoff-cta'))
    expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=investigation&sourceId=7')
  })

  it('renders workflow proof counts and switches to Open CAPA when actions exist', async () => {
    client.actionsApi.list.mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            title: 'Install barrier',
            status: 'open',
            source_type: 'investigation',
            source_id: 7,
          },
        ],
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-workflow-proof')).toBeInTheDocument()
    })

    const proof = screen.getByTestId('investigation-workflow-proof')
    expect(within(proof).getByText('investigations.handoff.proof_actions')).toBeInTheDocument()
    expect(within(proof).getAllByText('1')).toHaveLength(2)
    expect(screen.getByTestId('investigation-capa-handoff-cta')).toHaveTextContent(
      'investigations.handoff.open_capa',
    )
  })

  it('shows closure blockers with unblock path when open actions remain', async () => {
    client.investigationsApi.getClosureValidation.mockResolvedValue({
      data: {
        can_close: false,
        reasons: ['STATUS_NOT_COMPLETE', 'OPEN_ACTIONS_REMAIN'],
        open_work_count: 1,
        open_work: [
          {
            kind: 'investigation_action',
            id: 12,
            reference_number: 'INV-ACT-2026-0012',
            title: 'Replace guard',
            status: 'open',
            action_key: 'investigation_action:12',
            unblock_hint: 'Complete or cancel this action on the Actions tab.',
          },
        ],
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-closure-checklist')).toBeInTheDocument()
    })

    expect(screen.getByTestId('closure-blocker-12')).toHaveTextContent('INV-ACT-2026-0012')
    expect(screen.getByTestId('investigation-closure-go-actions')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('investigation-closure-go-actions'))
    expect(screen.getByTestId('investigation-actions-panel')).toBeInTheDocument()
  })

  it('shows unavailable CAPA counts instead of faux zero when actions fail', async () => {
    const { toast } = await import('../../contexts/ToastContext')
    client.actionsApi.list.mockRejectedValue(new Error('actions down'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-capa-count')).toHaveTextContent('—')
    })

    expect(toast.error).toHaveBeenCalled()
    expect(screen.queryByText('investigations.handoff.no_actions')).not.toBeInTheDocument()
    expect(screen.getByTestId('investigation-capa-handoff-cta')).toHaveTextContent(
      'investigations.handoff.create_action',
    )
  })

  it('shows honest closure unavailable state with retry when probe fails', async () => {
    client.investigationsApi.getClosureValidation.mockRejectedValue(new Error('closure down'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-closure-unavailable')).toBeInTheDocument()
    })

    expect(screen.getByText('investigations.closure.unavailable_title')).toBeInTheDocument()
    expect(screen.queryByText('Unable to load closure validation.')).not.toBeInTheDocument()

    client.investigationsApi.getClosureValidation.mockResolvedValue({
      data: { can_close: false, reasons: ['STATUS_NOT_COMPLETE'] },
    })
    fireEvent.click(screen.getByTestId('investigation-closure-retry'))

    await waitFor(() => {
      expect(screen.getByTestId('investigation-closure-checklist')).toBeInTheDocument()
    })
  })


  it('shows Close CTA when can_close and PATCHes status=closed', async () => {
    client.investigationsApi.getClosureValidation.mockResolvedValue({
      data: { can_close: true, reasons: [], open_work_count: 0, open_work: [] },
    })
    client.investigationsApi.update.mockResolvedValue({
      data: { ...mockInvestigation, status: 'closed' },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-close-cta')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('investigation-close-cta'))

    // Close now goes through the summary dialog rather than firing immediately.
    await waitFor(() => {
      expect(screen.getByTestId('investigation-close-summary-dialog')).toBeInTheDocument()
    })
    expect(client.investigationsApi.update).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('investigation-close-summary-confirm'))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalledWith(7, { status: 'closed' })
    })
  })

  it('offers Reopen on a closed investigation and PATCHes status=under_review', async () => {
    client.investigationsApi.get.mockResolvedValue({
      data: { ...mockInvestigation, status: 'closed' },
    })
    client.investigationsApi.getClosureValidation.mockResolvedValue({
      data: { can_close: true, reasons: [], open_work_count: 0, open_work: [] },
    })
    client.investigationsApi.update.mockResolvedValue({
      data: { ...mockInvestigation, status: 'under_review' },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-reopen')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('investigation-reopen'))
    fireEvent.click(await screen.findByTestId('investigation-reopen-confirm'))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalledWith(7, { status: 'under_review' })
    })
  })

  it('surfaces Report pack list errors honestly', async () => {
    client.investigationsApi.getPacks.mockRejectedValue(new Error('packs unavailable'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    await waitFor(() => {
      expect(screen.getByText('packs unavailable')).toBeInTheDocument()
    })
  })

  it('shows live CAPA handoff strip and interactive status workflow (Wave 2)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-capa-handoff-strip')).toBeInTheDocument()
    })

    expect(screen.getByTestId('investigation-status-workflow')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-workflow-in_progress')).toBeInTheDocument()
    expect(screen.getByTestId('investigation-capa-count')).toBeInTheDocument()
  })

  it('offers Create CAPA from root cause on RCA tab (Wave 2)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'RCA' }))

    await waitFor(() => {
      expect(screen.getByTestId('investigation-rca-create-capa')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('investigation-rca-create-capa'))
    expect(screen.getByTestId('investigation-actions-panel')).toBeInTheDocument()
  })

  it('jumps from closure blocker to CAPA by action_key (Wave 2)', async () => {
    client.investigationsApi.getClosureValidation.mockResolvedValue({
      data: {
        can_close: false,
        reasons: ['OPEN_ACTIONS_REMAIN'],
        open_work_count: 1,
        open_work: [
          {
            kind: 'investigation_action',
            id: 12,
            reference_number: 'INV-ACT-2026-0012',
            title: 'Replace guard',
            status: 'open',
            action_key: 'investigation_action:12',
            unblock_hint: 'Complete or cancel this action on the Actions tab.',
          },
        ],
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('closure-blocker-jump-investigation_action:12')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('closure-blocker-jump-investigation_action:12'))
    expect(screen.getByTestId('investigation-actions-panel')).toBeInTheDocument()
  })

  it('shows customer-pack omit controls on Report sections (SEV-C)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    await waitFor(() => {
      expect(screen.getByTestId('investigation-hsg245-report-sections')).toBeInTheDocument()
    })

    expect(screen.getByTestId('report-section-omit-request-event-details')).toBeInTheDocument()
    expect(screen.getByTestId('report-section-omit-approve-event-details')).toBeInTheDocument()
  })

  it('saves a typed lead investigator name and clears the user FK', async () => {
    client.investigationsApi.update.mockResolvedValue({ data: mockInvestigation })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-assignee-input')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('investigation-assignee-input'), {
      target: { value: 'External investigator' },
    })
    fireEvent.click(screen.getByTestId('investigation-summary-save'))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalledWith(
        7,
        expect.objectContaining({
          assigned_to_user_id: null,
          data: expect.objectContaining({ lead_investigator: 'External investigator' }),
        }),
      )
    })
  })

  it('writes assigned_to_user_id when a roster colleague is picked', async () => {
    client.investigationsApi.update.mockResolvedValue({ data: mockInvestigation })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-assignee-input-pick')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('investigation-assignee-input-pick'))
    fireEvent.click(screen.getByTestId('investigation-summary-save'))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalledWith(
        7,
        expect.objectContaining({
          assigned_to_user_id: 4,
          data: expect.objectContaining({ lead_investigator: 'david@example.com' }),
        }),
      )
    })
  })

  // INV-C4: the report path walks data.sections only, so a save must land in both
  // shapes. INV-C7 moved `findings` off this form onto its own rows, so the field
  // exercising the dual-write here is `conclusion` — same handler, same helper.
  it('saves the conclusion to the nested section as well as the flat key', async () => {
    client.investigationsApi.update.mockResolvedValue({ data: mockInvestigation })
    client.investigationsApi.get.mockResolvedValue({
      data: {
        ...mockInvestigation,
        data: { source_snapshot: { reference_number: 'RTA-42' }, sections: { section_1_details: { location: 'yard' } } },
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-conclusion-input')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('investigation-conclusion-input'), {
      target: { value: 'Unsafe system of work' },
    })
    fireEvent.click(screen.getByTestId('investigation-summary-save'))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalled()
    })

    const payload = client.investigationsApi.update.mock.calls[0][1].data
    expect(payload.conclusion).toBe('Unsafe system of work')
    expect(payload.sections.section_3_investigation_findings.conclusion).toBe(
      'Unsafe system of work',
    )
    // Unrelated data survives the dual-write.
    expect(payload.sections.section_1_details).toEqual({ location: 'yard' })
    expect(payload.source_snapshot).toEqual({ reference_number: 'RTA-42' })
  })

  // INV-C7: the rows are the only author of `findings`. A summary save that still
  // carried a copy of the string would overwrite whatever the row editor just did.
  it('does not write findings from the summary save any more', async () => {
    client.investigationsApi.update.mockResolvedValue({ data: mockInvestigation })
    client.investigationsApi.get.mockResolvedValue({
      data: {
        ...mockInvestigation,
        data: {
          findings: 'Guard was removed',
          sections: {
            section_3_investigation_findings: {
              findings: 'Guard was removed',
            },
          },
        },
      },
    })
    client.investigationsApi.listFindings.mockResolvedValue(
      findingsResponse(['Guard was removed']),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-conclusion-input')).toBeInTheDocument()
    })
    fireEvent.change(screen.getByTestId('investigation-conclusion-input'), {
      target: { value: 'Unsafe system of work' },
    })
    fireEvent.click(screen.getByTestId('investigation-summary-save'))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalled()
    })

    const payload = client.investigationsApi.update.mock.calls[0][1].data
    // Findings rows are the only author of either derived string.
    expect(payload.findings).toBeUndefined()
    expect(payload.sections?.section_3_investigation_findings?.findings).toBeUndefined()
  })

  it('saves RCA whys to the contract section and the legacy rca alias', async () => {
    client.investigationsApi.update.mockResolvedValue({ data: mockInvestigation })
    client.investigationsApi.get.mockResolvedValue({
      data: {
        ...mockInvestigation,
        data: {
          findings: 'Stale flat findings',
          sections: {
            section_3_investigation_findings: { findings: 'Stale nested findings' },
          },
        },
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'RCA' }))

    fireEvent.change(await screen.findByLabelText('Why 1?'), {
      target: { value: 'The driver could not see the walkway' },
    })
    fireEvent.change(screen.getByTestId('investigation-root-cause-input'), {
      target: { value: 'No banksman on site' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'investigations.save_rca' }))

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalled()
    })

    const payload = client.investigationsApi.update.mock.calls[0][1].data
    expect(payload.why_1).toBe('The driver could not see the walkway')
    for (const sectionKey of ['section_4_root_cause', 'rca']) {
      expect(payload.sections[sectionKey].why_1).toBe('The driver could not see the walkway')
      expect(payload.sections[sectionKey].root_cause).toBe('No banksman on site')
    }
    expect(payload.findings).toBeUndefined()
    expect(payload.sections.section_3_investigation_findings.findings).toBeUndefined()
  })

  it('hydrates the conclusion and whys from nested sections when the flat keys are empty', async () => {
    client.investigationsApi.get.mockResolvedValue({
      data: {
        ...mockInvestigation,
        data: {
          findings: '',
          sections: {
            section_3_investigation_findings: {
              findings: 'Nested finding from the template run',
              conclusion: 'Nested conclusion',
            },
            section_4_root_cause: { why_1: 'Nested why one' },
          },
        },
      },
    })
    // INV-C7: the nested findings string is converted to rows server-side; the page
    // reads the rows, not the JSON.
    client.investigationsApi.listFindings.mockResolvedValue(
      findingsResponse(['Nested finding from the template run']),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('investigation-conclusion-input')).toHaveValue('Nested conclusion')
    })
    expect(screen.getByTestId('investigation-finding-body-1')).toHaveTextContent(
      'Nested finding from the template run',
    )

    fireEvent.click(screen.getByRole('button', { name: 'RCA' }))
    expect(await screen.findByLabelText('Why 1?')).toHaveValue('Nested why one')
  })

  // ── INV-C7: the findings list editor ─────────────────────

  it('hydrates the findings editor from the findings endpoint', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(
      findingsResponse(['Guard was removed', 'No banksman present']),
    )

    renderPage()

    await waitFor(() => {
      expect(client.investigationsApi.listFindings).toHaveBeenCalledWith(7)
    })
    expect(await screen.findByTestId('investigation-finding-body-1')).toHaveTextContent(
      'Guard was removed',
    )
    expect(screen.getByTestId('investigation-finding-body-2')).toHaveTextContent(
      'No banksman present',
    )
    expect(screen.queryByTestId('investigation-findings-empty')).not.toBeInTheDocument()
  })

  it('says so plainly when a run has no findings yet', async () => {
    renderPage()

    expect(await screen.findByTestId('investigation-findings-empty')).toBeInTheDocument()
  })

  it('adds a finding and renders the list the server returns', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(findingsResponse([]))
    client.investigationsApi.createFinding.mockResolvedValue(
      findingsResponse(['Guard was removed']),
    )

    renderPage()

    const input = await screen.findByTestId('investigation-finding-new-input')
    fireEvent.change(input, { target: { value: '  Guard was removed  ' } })
    fireEvent.click(screen.getByTestId('investigation-finding-add'))

    await waitFor(() => {
      expect(client.investigationsApi.createFinding).toHaveBeenCalledWith(7, 'Guard was removed')
    })
    expect(await screen.findByTestId('investigation-finding-body-1')).toHaveTextContent(
      'Guard was removed',
    )
    // The draft box is cleared only once the call has succeeded.
    expect(screen.getByTestId('investigation-finding-new-input')).toHaveValue('')
  })

  it('silently refreshes findings without losing unsaved summary or RCA state', async () => {
    let resolveRefresh!: (value: { data: typeof mockInvestigation }) => void
    const refresh = new Promise<{ data: typeof mockInvestigation }>((resolve) => {
      resolveRefresh = resolve
    })
    client.investigationsApi.get
      .mockResolvedValueOnce({ data: mockInvestigation })
      .mockReturnValueOnce(refresh)
    client.investigationsApi.createFinding.mockResolvedValue(
      findingsResponse(['Guard was removed']),
    )

    renderPage()

    await screen.findByRole('heading', { name: 'Collision investigation' })
    fireEvent.click(screen.getByRole('button', { name: 'RCA' }))
    const rootCause = await screen.findByTestId('investigation-root-cause-input')
    fireEvent.change(rootCause, { target: { value: 'Unsaved root cause' } })
    fireEvent.click(screen.getByRole('button', { name: 'Summary' }))

    const conclusion = await screen.findByTestId('investigation-conclusion-input')
    fireEvent.change(conclusion, { target: { value: 'Unsaved conclusion' } })
    fireEvent.change(screen.getByTestId('investigation-finding-new-input'), {
      target: { value: 'Guard was removed' },
    })
    fireEvent.click(screen.getByTestId('investigation-finding-add'))

    await waitFor(() => {
      expect(client.investigationsApi.get).toHaveBeenCalledTimes(2)
    })
    // The full-page loading skeleton must not replace dirty editors while refreshing.
    expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    expect(conclusion).toHaveValue('Unsaved conclusion')

    await act(async () => {
      resolveRefresh({
        data: { ...mockInvestigation, title: 'Collision investigation refreshed' },
      })
      await refresh
    })
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Collision investigation refreshed' }),
      ).toBeInTheDocument()
    })
    expect(conclusion).toHaveValue('Unsaved conclusion')
    expect(screen.getByTestId('investigation-summary-save')).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'RCA' }))
    expect(await screen.findByTestId('investigation-root-cause-input')).toHaveValue(
      'Unsaved root cause',
    )
  })

  it('keeps a failed add draft in the editor', async () => {
    client.investigationsApi.createFinding.mockRejectedValue(new Error('Findings are locked'))

    renderPage()

    const input = await screen.findByTestId('investigation-finding-new-input')
    fireEvent.change(input, { target: { value: 'Guard was removed' } })
    fireEvent.click(screen.getByTestId('investigation-finding-add'))

    expect(await screen.findByTestId('investigation-findings-error')).toHaveTextContent(
      'Findings are locked',
    )
    expect(input).toHaveValue('Guard was removed')
  })

  it('refuses to add a blank finding', async () => {
    renderPage()

    const input = await screen.findByTestId('investigation-finding-new-input')
    fireEvent.change(input, { target: { value: '   ' } })

    expect(screen.getByTestId('investigation-finding-add')).toBeDisabled()
    fireEvent.click(screen.getByTestId('investigation-finding-add'))
    expect(client.investigationsApi.createFinding).not.toHaveBeenCalled()
  })

  it('edits one finding in place', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(findingsResponse(['typo']))
    client.investigationsApi.updateFinding.mockResolvedValue(
      findingsResponse(['Guard was removed']),
    )

    renderPage()

    fireEvent.click(await screen.findByTestId('investigation-finding-edit-1'))
    fireEvent.change(screen.getByTestId('investigation-finding-edit-input-1'), {
      target: { value: 'Guard was removed' },
    })
    fireEvent.click(screen.getByTestId('investigation-finding-save-1'))

    await waitFor(() => {
      expect(client.investigationsApi.updateFinding).toHaveBeenCalledWith(
        7,
        1,
        'Guard was removed',
      )
    })
    expect(await screen.findByTestId('investigation-finding-body-1')).toHaveTextContent(
      'Guard was removed',
    )
  })

  it('keeps a failed edit draft in the editor', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(findingsResponse(['typo']))
    client.investigationsApi.updateFinding.mockRejectedValue(new Error('Findings are locked'))

    renderPage()

    fireEvent.click(await screen.findByTestId('investigation-finding-edit-1'))
    const input = screen.getByTestId('investigation-finding-edit-input-1')
    fireEvent.change(input, { target: { value: 'Guard was removed' } })
    fireEvent.click(screen.getByTestId('investigation-finding-save-1'))

    expect(await screen.findByTestId('investigation-findings-error')).toHaveTextContent(
      'Findings are locked',
    )
    expect(input).toHaveValue('Guard was removed')
  })

  it('removes a finding', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(
      findingsResponse(['Guard was removed', 'No banksman present']),
    )
    client.investigationsApi.deleteFinding.mockResolvedValue(findingsResponse([]))

    renderPage()

    fireEvent.click(await screen.findByTestId('investigation-finding-delete-1'))

    await waitFor(() => {
      expect(client.investigationsApi.deleteFinding).toHaveBeenCalledWith(7, 1)
    })
    expect(await screen.findByTestId('investigation-findings-empty')).toBeInTheDocument()
  })

  // The endpoint refuses a partial list, so a move has to send every id.
  it('reorders by sending the complete id list in the wanted order', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(
      findingsResponse(['first', 'second', 'third']),
    )
    client.investigationsApi.reorderFindings.mockResolvedValue(
      findingsResponse(['first', 'third', 'second']),
    )

    renderPage()

    fireEvent.click(await screen.findByTestId('investigation-finding-down-2'))

    await waitFor(() => {
      expect(client.investigationsApi.reorderFindings).toHaveBeenCalledWith(7, [1, 3, 2])
    })
    const rows = screen.getByTestId('investigation-findings-list').querySelectorAll('li')
    expect(rows[1]).toHaveTextContent('third')
    expect(rows[2]).toHaveTextContent('second')
  })

  it('cannot move the first finding up or the last one down', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(findingsResponse(['first', 'second']))

    renderPage()

    expect(await screen.findByTestId('investigation-finding-up-1')).toBeDisabled()
    expect(screen.getByTestId('investigation-finding-down-2')).toBeDisabled()
  })

  it('keeps the previous list and reports the reason when a findings write fails', async () => {
    client.investigationsApi.listFindings.mockResolvedValue(findingsResponse(['Guard was removed']))
    client.investigationsApi.deleteFinding.mockRejectedValue(new Error('Findings are locked'))

    renderPage()

    fireEvent.click(await screen.findByTestId('investigation-finding-delete-1'))

    expect(await screen.findByTestId('investigation-findings-error')).toHaveTextContent(
      'Findings are locked',
    )
    // Nothing was removed optimistically.
    expect(screen.getByTestId('investigation-finding-body-1')).toHaveTextContent(
      'Guard was removed',
    )
  })

  it('lists source-linked evidence as well as investigation uploads', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Evidence' }))

    await waitFor(() => {
      expect(client.evidenceAssetsApi.list).toHaveBeenCalledWith({
        source_module: 'investigation',
        source_id: 7,
        page: 1,
        page_size: 50,
      })
      expect(client.evidenceAssetsApi.list).toHaveBeenCalledWith({
        linked_investigation_id: 7,
        page: 1,
        page_size: 50,
      })
    })
  })
})
