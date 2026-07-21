import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Portal from '../Portal'

const mockMyCompliance = vi.fn()
const mockListMyAssignments = vi.fn()
const mockMyTraining = vi.fn()
const mockAnnounce = vi.fn()

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    listMyAssignments: (...args: unknown[]) => mockListMyAssignments(...args),
  },
  trainingMatrixApi: {
    myTraining: (...args: unknown[]) => mockMyTraining(...args),
  },
  portalComplianceApi: {
    myCompliance: (...args: unknown[]) => mockMyCompliance(...args),
  },
}))

vi.mock('../../contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({
    user: { name: 'Test Engineer', email: 'eng@example.com' },
    logout: vi.fn(),
  }),
}))

vi.mock('../../components/ui/LiveAnnouncer', () => ({
  useLiveAnnouncer: () => ({ announce: mockAnnounce }),
}))

vi.mock('../../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => null,
}))

vi.mock('../../components/BrandMark', () => ({
  BrandMarkTile: () => null,
}))

describe('Portal tools + van landing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListMyAssignments.mockResolvedValue({ data: { items: [] } })
    mockMyTraining.mockResolvedValue({ items: [] })
  })

  it('shows clear-to-work and tool/van actions before report', async () => {
    mockMyCompliance.mockResolvedValue({
      clear_state: 'attention',
      tool_summary: {
        total: 2,
        overdue: 1,
        due_30: 0,
        due_60: 0,
        due_90: 0,
        in_date: 1,
        quarantined: 0,
        mine: 1,
        on_van: 1,
      },
      tool_badge: 1,
      van_summary: {
        vehicle_reg: 'AB12CDE',
        daily_last_at: null,
        daily_pass: null,
        monthly_last_at: null,
        defect_counts: { p1: 0, p2: 1, p3: 0, total: 1 },
        empty_reason: null,
        assignment_conflict: false,
      },
      van_badge: 1,
      tools_empty_reason: null,
    })

    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-clear-to-work')).toBeInTheDocument()
    })
    expect(screen.getByText('Needs attention')).toBeInTheDocument()
    expect(screen.getByTestId('portal-tools-btn')).toBeInTheDocument()
    expect(screen.getByTestId('portal-van-btn')).toBeInTheDocument()
    expect(screen.getByTestId('portal-tools-badge')).toHaveTextContent('1')
    expect(screen.getByTestId('portal-van-badge')).toHaveTextContent('1')

    const tools = screen.getByTestId('portal-tools-btn')
    const report = screen.getByTestId('portal-report-btn')
    expect(tools.compareDocumentPosition(report) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('shows honest fetch-failed state instead of fake zeros', async () => {
    mockMyCompliance.mockRejectedValue(new Error('offline'))

    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-compliance-failed')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('portal-clear-to-work')).not.toBeInTheDocument()
  })
})
