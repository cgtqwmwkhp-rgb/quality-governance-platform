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
  default: ({ investigation }: { investigation: { title: string } }) => (
    <div>
      <h1>{investigation.title}</h1>
    </div>
  ),
}))

vi.mock('../investigation/InvestigationTimeline', () => ({
  default: () => <div>Timeline</div>,
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
  },
  actionsApi: {
    list: vi.fn(),
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

  it('links back to the source record and into the CAPA workspace', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Collision investigation' })).toBeInTheDocument()
    })

    fireEvent.click(
      screen.getAllByRole('button', { name: 'investigations.handoff.back_to_source' })[0],
    )
    expect(mockNavigate).toHaveBeenCalledWith('/rtas/42')

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
})
