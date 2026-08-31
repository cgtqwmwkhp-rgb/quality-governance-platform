import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PortalAudits from '../PortalAudits'

const mockNavigate = vi.fn()
const mockListAssignedToMe = vi.fn()
const mockListRuns = vi.fn()
const mockListTemplates = vi.fn()
const mockCreateRun = vi.fn()
const mockToastError = vi.fn()
let mockSenior = false

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

vi.mock('../portalAuditSenior', () => ({
  isPortalAuditSenior: () => mockSenior,
}))

vi.mock('../../utils/auth', () => ({
  getCurrentUserId: () => 7,
}))

vi.mock('../../api/client', () => ({
  auditsApi: {
    listAssignedToMe: (...args: unknown[]) => mockListAssignedToMe(...args),
    listRuns: (...args: unknown[]) => mockListRuns(...args),
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
    createRun: (...args: unknown[]) => mockCreateRun(...args),
  },
  getApiErrorMessage: () => 'Network down',
}))

describe('PortalAudits', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSenior = false
    mockListAssignedToMe.mockResolvedValue({ data: { total: 0, items: [] } })
    mockListRuns.mockResolvedValue({ data: { total: 0, items: [] } })
    mockListTemplates.mockResolvedValue({ data: { total: 0, items: [] } })
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
    expect(screen.queryByTestId('portal-audits-catalogue')).not.toBeInTheDocument()
    expect(mockListRuns).not.toHaveBeenCalled()

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

  it('lets a senior filter completed runs and start a published template', async () => {
    mockSenior = true
    mockListRuns.mockResolvedValue({
      data: {
        total: 1,
        items: [
          {
            id: 90,
            reference_number: 'AUD-90',
            title: 'Yard inspection',
            status: 'completed',
            location: 'Bedford',
          },
        ],
      },
    })
    mockListTemplates.mockResolvedValue({
      data: {
        total: 1,
        items: [{ id: 3, name: 'ISO 45001 walk', audit_type: 'inspection', is_published: true }],
      },
    })
    mockCreateRun.mockResolvedValue({ data: { id: 101 } })

    render(
      <MemoryRouter>
        <PortalAudits />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('portal-audits-catalogue')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByTestId('portal-catalogue-progress-completed'))
    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledWith(1, 100, expect.objectContaining({ progress: 'completed' }))
    })
    await waitFor(() => {
      expect(screen.getByTestId('portal-catalogue-run-90')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByTestId('portal-catalogue-open-90'))
    expect(mockNavigate).toHaveBeenCalledWith('/audits/90/execute')

    await userEvent.click(screen.getByTestId('portal-catalogue-start-3'))
    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledWith({
        template_id: 3,
        title: 'ISO 45001 walk',
        assigned_to_id: 7,
      })
    })
    expect(mockNavigate).toHaveBeenCalledWith('/audits/101/execute')
  })
})
