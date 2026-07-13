import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Actions from '../Actions'

const mockList = vi.fn()
const mockSummary = vi.fn()
const mockGetDeliveryStatus = vi.fn()
const mockToastError = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      ({
        'actions.view_finding': 'View finding',
        'actions.view_mode.all': 'All',
        'actions.view_mode.my': 'My actions',
        'actions.view_mode.overdue': 'Overdue',
        'actions.email_unavailable.title': 'Email alerts unavailable',
        'actions.email_unavailable.body':
          'The assignee is saved, but email alerts are unavailable while outbound email is not configured.',
        'actions.filter.identity_required':
          'Cannot load My actions — signed-in user id is unavailable.',
        'actions.filter.server_failed':
          'Server filter failed — results were not loaded. Try again or switch to All.',
        'actions.filter.server_my':
          'Showing actions assigned to you (server filter: assigned_to=me).',
        'actions.filter.server_overdue':
          'Showing overdue open actions (server filter: overdue=true).',
      } as Record<string, string>)[key] || fallback || key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  actionsApi: {
    list: (...args: unknown[]) => mockList(...args),
    summary: (...args: unknown[]) => mockSummary(...args),
    create: vi.fn(),
  },
  notificationsApi: {
    getDeliveryStatus: (...args: unknown[]) => mockGetDeliveryStatus(...args),
  },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}))

vi.mock('../../utils/auth', () => ({
  getPlatformToken: () => 'fake.token',
  decodeTokenPayload: () => ({ sub: '42' }),
}))

const action = (overrides: Record<string, unknown>) => ({
  id: 1,
  reference_number: 'ACT-0001',
  title: 'Correct audit finding',
  description: 'Resolve the finding',
  action_type: 'corrective',
  priority: 'high',
  status: 'open',
  display_status: 'open',
  action_key: 'capa:1',
  source_type: 'audit_finding',
  source_id: 42,
  owner_id: 42,
  created_at: '2026-07-12T10:00:00Z',
  ...overrides,
})

describe('Actions finding deep-link', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSummary.mockResolvedValue({ data: { total: 3, by_display_status: { open: 3 } } })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
    mockList.mockResolvedValue({ data: { items: [action({})] } })
  })

  it('links only audit-finding rows with a positive source id', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [
          action({ id: 1, action_key: 'capa:1', source_id: 42 }),
          action({ id: 2, action_key: 'capa:2', source_id: 0 }),
          action({ id: 3, action_key: 'incident_action:3', source_type: 'incident', source_id: 7 }),
        ],
      },
    })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    const links = await screen.findAllByRole('link', { name: 'View finding' })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/audits?view=findings&findingId=42')
  })

  it('warns that CAPA assignment does not imply email delivery', async () => {
    mockList.mockResolvedValue({ data: { items: [action({})] } })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: false } })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Email alerts unavailable')).toBeInTheDocument()
    expect(
      screen.getByText(
        'The assignee is saved, but email alerts are unavailable while outbound email is not configured.',
      ),
    ).toBeInTheDocument()
  })
})

describe('Actions My Work / Overdue server filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSummary.mockResolvedValue({ data: { total: 1, by_display_status: { open: 1 } } })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
    mockList.mockResolvedValue({ data: { items: [action({})] } })
  })

  it('requests assigned_to=me when My actions is selected', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByText('Correct audit finding')
    await user.click(screen.getByTestId('actions-view-my'))

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(
        1,
        100,
        undefined,
        undefined,
        undefined,
        { assigned_to: 'me', overdue: undefined },
      )
    })
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'assigned_to=me',
    )
  })

  it('requests overdue=true when Overdue is selected', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByText('Correct audit finding')
    await user.click(screen.getByTestId('actions-view-overdue'))

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(
        1,
        100,
        undefined,
        undefined,
        undefined,
        { assigned_to: undefined, overdue: true },
      )
    })
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'overdue=true',
    )
  })

  it('toasts and labels when the My/Overdue server filter request fails', async () => {
    const user = userEvent.setup()
    mockList.mockImplementation(
      (
        _page?: number,
        _size?: number,
        _status?: string,
        _sourceType?: string,
        _sourceId?: number,
        scope?: { assigned_to?: string; overdue?: boolean },
      ) => {
        if (scope?.overdue) {
          return Promise.reject(new Error('500 server'))
        }
        return Promise.resolve({ data: { items: [action({})] } })
      },
    )

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByText('Correct audit finding')
    await user.click(screen.getByTestId('actions-view-overdue'))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        'Server filter failed — results were not loaded. Try again or switch to All.',
      )
    })
    expect(await screen.findByTestId('actions-filter-error')).toHaveTextContent(
      'Server filter failed',
    )
  })
})
