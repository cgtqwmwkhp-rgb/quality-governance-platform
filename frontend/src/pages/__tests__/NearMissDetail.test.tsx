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
    listInvestigations: vi.fn(),
    listRunningSheet: vi.fn(),
  },
  investigationsApi: {
    createFromRecord: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
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
  status: 'REPORTED',
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
})
