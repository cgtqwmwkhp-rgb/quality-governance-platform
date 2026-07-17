import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
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
  triggerPackDownload: vi.fn(),
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
    expect(toast.success).toHaveBeenCalledWith('investigations.report.download_stub_success')
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
    expect(screen.getByTestId('investigation-findings-input')).toBeInTheDocument()
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

    await waitFor(() => {
      expect(client.investigationsApi.update).toHaveBeenCalledWith(7, { status: 'closed' })
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
})
