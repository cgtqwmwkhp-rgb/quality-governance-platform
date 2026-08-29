import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PortalAudits from '../PortalAudits'

const mockNavigate = vi.fn()
const mockListAssignedToMe = vi.fn()
const mockToastError = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../components/ui/LiveAnnouncer', () => ({
  useLiveAnnouncer: () => ({ announce: vi.fn() }),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: (...args: unknown[]) => mockToastError(...args) },
}))

vi.mock('../../api/client', () => ({
  auditsApi: {
    listAssignedToMe: (...args: unknown[]) => mockListAssignedToMe(...args),
  },
  getApiErrorMessage: () => 'Network down',
}))

describe('PortalAudits', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('lists assigned runs and discloses the staff-shell hop', async () => {
    mockListAssignedToMe.mockResolvedValue({
      data: {
        total: 1,
        items: [
          {
            id: 44,
            reference_number: 'AUD-44',
            title: 'Bedford yard inspection',
            status: 'scheduled',
            location: 'Bedford yard',
          },
        ],
      },
    })

    render(
      <MemoryRouter>
        <PortalAudits />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-audit-row-44')).toBeInTheDocument()
    })
    expect(
      screen.getByText(/Opening an audit uses the staff audit workspace/i),
    ).toBeInTheDocument()

    await userEvent.click(screen.getByTestId('portal-audit-open-44'))
    expect(mockNavigate).toHaveBeenCalledWith('/audits/44/execute')
  })

  it('does not render ??? or unknown rows', async () => {
    mockListAssignedToMe.mockResolvedValue({
      data: {
        total: 2,
        items: [
          { id: 1, reference_number: '???', status: 'scheduled', title: 'Broken' },
          { id: 2, reference_number: 'AUD-2', status: 'unknown', title: 'Unknown' },
        ],
      },
    })

    render(
      <MemoryRouter>
        <PortalAudits />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('No audits assigned to you')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('portal-audit-row-1')).not.toBeInTheDocument()
  })

  it('shows an error instead of an empty queue when the request fails', async () => {
    mockListAssignedToMe.mockRejectedValue(new Error('fail'))

    render(
      <MemoryRouter>
        <PortalAudits />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-audits-error')).toBeInTheDocument()
    })
    expect(screen.queryByText('No audits assigned to you')).not.toBeInTheDocument()
  })
})
