import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Portal from '../Portal'

const mockNavigate = vi.fn()
const mockListMyAssignments = vi.fn()
const mockActionsList = vi.fn()
const mockMyTraining = vi.fn()
const mockMyCompliance = vi.fn()
const mockListAssignedToMe = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({
    user: { name: 'Alex Engineer', email: 'alex@example.com' },
    logout: vi.fn(),
  }),
}))

vi.mock('../../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => null,
}))

vi.mock('../../components/ui/LiveAnnouncer', () => ({
  useLiveAnnouncer: () => ({ announce: vi.fn() }),
}))

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    listMyAssignments: (...args: unknown[]) => mockListMyAssignments(...args),
  },
  actionsApi: {
    list: (...args: unknown[]) => mockActionsList(...args),
  },
  trainingMatrixApi: {
    myTraining: (...args: unknown[]) => mockMyTraining(...args),
  },
  portalComplianceApi: {
    myCompliance: (...args: unknown[]) => mockMyCompliance(...args),
  },
  auditsApi: {
    listAssignedToMe: (...args: unknown[]) => mockListAssignedToMe(...args),
  },
}))

describe('Portal hub honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListMyAssignments.mockResolvedValue({
      data: { items: [{ status: 'pending' }] },
    })
    mockActionsList.mockResolvedValue({
      data: {
        total: 9,
        items: Array.from({ length: 9 }, () => ({ status: 'open' })),
      },
    })
    mockMyTraining.mockResolvedValue({ items: [] })
    mockMyCompliance.mockResolvedValue({
      clear_state: 'clear',
      tool_badge: 0,
      van_badge: 0,
      tool_summary: { total: 0, overdue: 0 },
      van_summary: { empty_reason: 'no_van' },
    })
    mockListAssignedToMe.mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('uses keyboard-focusable buttons for track and help tiles (PX-295)', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('portal-track-btn').tagName).toBe('BUTTON')
    expect(screen.getByTestId('portal-help-btn').tagName).toBe('BUTTON')
  })

  it('counts assigned actions plus pending reading on My Work badge (PX-305)', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-work-pending-count')).toHaveTextContent('10')
    })
  })

  it('does not advertise reference lookup on the track tile (PX-319)', () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    expect(screen.getByText('View your submitted reports and status')).toBeInTheDocument()
    expect(screen.queryByText('Check status with reference number')).not.toBeInTheDocument()
  })

  it('does not render the admin login footer (PX-297)', () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    expect(screen.queryByText('Admin Login →')).not.toBeInTheDocument()
  })

  it('deep-links training to the training section (PX-321)', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await user.click(screen.getByTestId('portal-training-btn'))
    expect(mockNavigate).toHaveBeenCalledWith('/portal/work#training')
  })

  it('shows an explicit empty Audits tile from the server total, not a missing tile', async () => {
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-audits-subtitle')).toHaveTextContent(
        'No audits assigned to you',
      )
    })
    expect(screen.queryByTestId('portal-audits-count')).not.toBeInTheDocument()
  })

  it('does not show a fake zero when assigned audits fail to load', async () => {
    mockListAssignedToMe.mockRejectedValue(new Error('offline'))
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-audits-subtitle')).toHaveTextContent(
        'Couldn’t load assigned audits',
      )
    })
    expect(screen.queryByTestId('portal-audits-count')).not.toBeInTheDocument()
    expect(screen.queryByTestId('portal-audits-badge')).not.toBeInTheDocument()
  })

  it('opens the portal Audits section from the hub tile', async () => {
    const user = userEvent.setup()
    mockListAssignedToMe.mockResolvedValue({ data: { items: [], total: 2 } })
    render(
      <MemoryRouter>
        <Portal />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-audits-count')).toHaveTextContent('2')
    })
    await user.click(screen.getByTestId('portal-audits-btn'))
    expect(mockNavigate).toHaveBeenCalledWith('/portal/audits')
  })
})
