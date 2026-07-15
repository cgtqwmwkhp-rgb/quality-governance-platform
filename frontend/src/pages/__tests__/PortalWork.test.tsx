import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import axios from 'axios'
import PortalWork from '../PortalWork'

const mockList = vi.fn()
const mockListMyPending = vi.fn()
const mockGetByUserMe = vi.fn()
const mockRecordOpen = vi.fn()
const mockToastError = vi.fn()
const mockAnnounce = vi.fn()

vi.mock('../../api/client', () => ({
  actionsApi: {
    list: (...args: unknown[]) => mockList(...args),
  },
  policyAcknowledgmentsApi: {
    listMyPending: (...args: unknown[]) => mockListMyPending(...args),
    recordOpen: (...args: unknown[]) => mockRecordOpen(...args),
  },
  engineersApi: {
    getByUserMe: (...args: unknown[]) => mockGetByUserMe(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Request failed',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}))

vi.mock('../../components/ui/LiveAnnouncer', () => ({
  useLiveAnnouncer: () => ({ announce: mockAnnounce }),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <PortalWork />
    </MemoryRouter>,
  )
}

describe('PortalWork CUJ-P10', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            title: 'Close CAPA',
            description: 'Do the thing',
            action_type: 'corrective',
            priority: 'high',
            status: 'open',
            display_status: 'open',
            action_key: 'capa:1',
            source_type: 'audit_finding',
            source_id: 9,
            due_date: '2020-01-01',
            created_at: '2026-07-01T10:00:00Z',
            reference_number: 'ACT-0001',
          },
        ],
        total: 1,
      },
    })
    mockListMyPending.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetByUserMe.mockResolvedValue({ data: { linked: false } })
  })

  it('requests assigned_to=me and renders action + unlinked passport', async () => {
    renderPage()

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 20, undefined, undefined, undefined, {
        assigned_to: 'me',
      })
    })

    expect(await screen.findByTestId('portal-work-actions')).toBeInTheDocument()
    expect(screen.getByText('Close CAPA')).toBeInTheDocument()
    expect(screen.getByTestId('portal-work-actions-filter-label')).toHaveTextContent(
      'assigned_to=me',
    )
    expect(await screen.findByTestId('portal-work-passport-unlinked')).toBeInTheDocument()
    expect(screen.getByText(/Contact your supervisor/i)).toBeInTheDocument()
    expect(screen.getByTestId('portal-work-reading')).toBeInTheDocument()
    expect(screen.getByText(/No pending reads/i)).toBeInTheDocument()
  })

  it('shows honest empty actions when server returns none', async () => {
    mockList.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetByUserMe.mockResolvedValue({
      data: {
        linked: true,
        id: 10,
        external_id: 'eng-1',
        user_id: 42,
        job_title: 'Field Engineer',
        employee_number: 'E-42',
        is_active: true,
      },
    })

    renderPage()

    expect(await screen.findByText(/No actions assigned to you/i)).toBeInTheDocument()
    expect(await screen.findByTestId('portal-work-passport-linked')).toBeInTheDocument()
    expect(screen.getByText('Field Engineer')).toBeInTheDocument()
  })

  it('surfaces actions filter failure without silent empty success', async () => {
    mockList.mockRejectedValue(new Error('Server filter failed'))
    mockGetByUserMe.mockResolvedValue({
      data: { linked: true, id: 10, external_id: 'e', user_id: 1, is_active: true },
    })

    renderPage()

    expect(await screen.findByTestId('portal-work-actions-error')).toBeInTheDocument()
    expect(mockToastError).toHaveBeenCalled()
  })
})
