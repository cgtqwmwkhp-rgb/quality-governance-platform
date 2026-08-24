import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) =>
      typeof fallback === 'string' ? fallback : key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))


vi.mock('../../components/EngineerPeoplePicker', () => ({
  EngineerPeoplePicker: ({ testId = 'engineer-people-picker' }: { testId?: string }) => (
    <input data-testid={testId} aria-label="Assign to" />
  ),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../../api/client', () => ({
  getApiErrorMessage: () => 'error',
  nearMissesApi: {
    get: vi.fn(),
    update: vi.fn(),
    listInvestigations: vi.fn(),
    listRunningSheet: vi.fn(),
  },
  investigationsApi: {
    createFromRecord: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
  },
  evidenceAssetsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  contractsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  lookupsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))

vi.mock('../../components/StandardsAssessmentPanel', () => ({
  StandardsAssessmentPanel: () => <div>Standards panel</div>,
}))

vi.mock('../../components/ui/Breadcrumbs', () => ({
  Breadcrumbs: () => null,
}))

vi.mock('../../components/ui/SkeletonLoader', () => ({
  CardSkeleton: () => <div>Loading</div>,
}))

vi.mock('../../components/case/CaseSummaryRail', () => ({
  CaseSummaryRail: () => null,
}))

vi.mock('../../components/case/RunningSheetPanel', () => ({
  RunningSheetPanel: () => null,
  buildRunningSheetCreateActionHref: () => '/actions/new',
}))

vi.mock('../../components/ui/Tabs', () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({
    children,
    ...rest
  }: {
    children: ReactNode
    'data-testid'?: string
  }) => (
    <button type="button" data-testid={rest['data-testid']}>
      {children}
    </button>
  ),
  TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock('../../components/ui/Dialog', () => ({
  Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

import * as client from '../../api/client'
import NearMissDetail from '../NearMissDetail'

const nearMiss = {
  id: 5,
  reference_number: 'NM-5',
  reporter_name: 'Alex',
  was_involved: true,
  contract: 'A',
  location: 'Yard',
  event_date: '2026-07-01T10:00:00Z',
  description: 'Near miss description long enough',
  witnesses_present: false,
  status: 'reported',
  priority: 'MEDIUM',
  created_at: '2026-07-01T10:00:00Z',
  updated_at: '2026-07-01T10:00:00Z',
}

describe('NearMissDetail investigation → CAPA honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(client.nearMissesApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: nearMiss })
    ;(client.nearMissesApi.listRunningSheet as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [],
    })
  })

  it('deep-links investigations and shows CAPA count', async () => {
    ;(client.nearMissesApi.listInvestigations as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [{ id: 21, reference_number: 'INV-21', title: 'Linked investigation', status: 'open' }],
        total: 1,
      },
    })
    ;(client.actionsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          { id: 1, title: 'CAPA 1', status: 'open' },
          { id: 2, title: 'CAPA 2', status: 'in_progress' },
        ],
        total: 2,
      },
    })

    render(
      <MemoryRouter initialEntries={['/near-misses/5']}>
        <Routes>
          <Route path="/near-misses/:id" element={<NearMissDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-investigation-21')).toBeInTheDocument()
    })
    expect(screen.getByTestId('near-miss-capa-count')).toHaveTextContent('2')
    expect(screen.getByTestId('near-miss-actions-tab')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('near-miss-investigation-21'))
    expect(mockNavigate).toHaveBeenCalledWith('/investigations/21')

    fireEvent.click(screen.getByTestId('near-miss-capa-handoff-cta'))
    expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=near_miss&sourceId=5')

    fireEvent.click(screen.getByTestId('near-miss-open-capa'))
    expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=near_miss&sourceId=5')
  })

  it('shows em dash when CAPA actions fail to load', async () => {
    ;(client.nearMissesApi.listInvestigations as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [{ id: 21, reference_number: 'INV-21', title: 'Linked investigation', status: 'open' }],
        total: 1,
      },
    })
    ;(client.actionsApi.list as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('boom'))

    render(
      <MemoryRouter initialEntries={['/near-misses/5']}>
        <Routes>
          <Route path="/near-misses/:id" element={<NearMissDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-capa-count')).toHaveTextContent('—')
    })
  })

  it('adds and saves structured witnesses on the shared Witnesses tab', async () => {
    ;(client.nearMissesApi.listInvestigations as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(client.actionsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(client.nearMissesApi.update as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { ...nearMiss, witnesses_structured: { witnesses: [{ name: 'Sam Bystander' }] } },
    })

    render(
      <MemoryRouter initialEntries={['/near-misses/5']}>
        <Routes>
          <Route path="/near-misses/:id" element={<NearMissDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-actions-tab')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('near-miss-witnesses-add'))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Sam Bystander' } })
    fireEvent.click(screen.getByTestId('near-miss-witnesses-save'))

    await waitFor(() => {
      expect(client.nearMissesApi.update).toHaveBeenCalledWith(
        5,
        expect.objectContaining({
          witnesses_structured: { witnesses: [expect.objectContaining({ name: 'Sam Bystander' })] },
        }),
      )
    })
  })

  it('renders the shared Photos tab wired to evidence-assets upload', async () => {
    ;(client.nearMissesApi.listInvestigations as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(client.actionsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })

    render(
      <MemoryRouter initialEntries={['/near-misses/5']}>
        <Routes>
          <Route path="/near-misses/:id" element={<NearMissDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-evidence-panel')).toBeInTheDocument()
    })
    expect(client.evidenceAssetsApi.list).toHaveBeenCalledWith({
      source_module: 'near_miss',
      source_id: 5,
      page_size: 50,
    })
  })
})

describe('NearMissDetail closure lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(client.nearMissesApi.listInvestigations as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(client.actionsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(client.nearMissesApi.listRunningSheet as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [],
    })
  })

  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/near-misses/5']}>
        <Routes>
          <Route path="/near-misses/:id" element={<NearMissDetail />} />
        </Routes>
      </MemoryRouter>,
    )

  it('offers Close on an open near miss and shows the status badge', async () => {
    ;(client.nearMissesApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: nearMiss })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-close')).toBeInTheDocument()
    })
    expect(screen.getByTestId('near-miss-status-badge')).toHaveTextContent('Reported')
    expect(screen.queryByTestId('near-miss-reopen')).not.toBeInTheDocument()
  })

  // N-2: the reopen target is the incident register's, not a near-miss-only one.
  it('reopens a closed near miss back to pending_review', async () => {
    ;(client.nearMissesApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { ...nearMiss, status: 'closed' },
    })
    ;(client.nearMissesApi.update as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { ...nearMiss, status: 'pending_review' },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-reopen')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('near-miss-reopen'))
    fireEvent.click(await screen.findByTestId('near-miss-reopen-confirm'))

    await waitFor(() => {
      expect(client.nearMissesApi.update).toHaveBeenCalledWith(5, { status: 'pending_review' })
    })
  })

  it('edits status through a Select, not free text', async () => {
    ;(client.nearMissesApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: nearMiss })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('near-miss-close')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Edit/i }))

    const statusControl = await screen.findByRole('combobox', { name: 'Status' })
    expect(statusControl).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Status' })).not.toBeInTheDocument()
  })
})
