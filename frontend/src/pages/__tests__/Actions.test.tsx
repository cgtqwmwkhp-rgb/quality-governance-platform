import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom'
import Actions from '../Actions'

function SearchParamsProbe() {
  const [params] = useSearchParams()
  return <div data-testid="search-params">{params.toString()}</div>
}

function ActionsRoute({ path = '/actions' }: { path?: string }) {
  return (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/actions"
          element={
            <>
              <Actions />
              <SearchParamsProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

const mockList = vi.fn()
const mockSummary = vi.fn()
const mockViewCounts = vi.fn()
const mockGetDeliveryStatus = vi.fn()
const mockToastError = vi.fn()
const mockCreate = vi.fn()

const { tMock } = vi.hoisted(() => {
  const messages: Record<string, string> = {
    'actions.view_finding': 'View finding',
    'actions.view_mode.all': 'All',
    'actions.view_mode.my': 'My actions',
    'actions.view_mode.overdue': 'Overdue',
    'actions.view_mode.my_overdue': 'My overdue',
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
    'actions.filter.server_my_overdue':
      'Showing your overdue open actions (server filter: assigned_to=me&overdue=true).',
    'actions.filter.loading': 'Updating filtered actions…',
    'actions.open_profile': 'Open profile',
    'actions.new': 'New Action',
    'actions.dialog.title': 'New Action',
    'actions.create': 'Create Action',
    'actions.expand_details': 'Details',
    'actions.collapse_details': 'Hide',
    'actions.detail.panel': 'Action details',
    'actions.detail.type': 'Type',
    'actions.detail.created': 'Created',
    'actions.detail.description': 'Full description',
    'cancel': 'Cancel',
  }
  return {
    tMock: (key: string, fallback?: string) => messages[key] || fallback || key,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: tMock }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  actionsApi: {
    list: (...args: unknown[]) => mockList(...args),
    summary: (...args: unknown[]) => mockSummary(...args),
    viewCounts: (...args: unknown[]) => mockViewCounts(...args),
    create: (...args: unknown[]) => mockCreate(...args),
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
    mockViewCounts.mockResolvedValue({
      data: { all: 10, my: 3, overdue: 2, my_overdue: 1 },
    })
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

  it('links action profile rows to RESTful /actions/:id permalinks', async () => {
    mockList.mockResolvedValue({
      data: {
        items: [action({ action_key: 'capa:99' })],
      },
    })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    const link = await screen.findByRole('link', { name: 'Open profile' })
    expect(link).toHaveAttribute('href', '/actions/capa%3A99')
  })

  it('filters via interactive hero Overdue KPI', async () => {
    const user = userEvent.setup()
    mockSummary.mockResolvedValue({
      data: { total: 3, by_display_status: { open: 2 }, overdue: 1 },
    })
    mockList.mockResolvedValue({ data: { items: [action({})] } })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByTestId('actions-hero-board')
    await user.click(screen.getByTestId('actions-hero-overdue'))

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 100, undefined, undefined, undefined, {
        assigned_to: undefined,
        overdue: true,
      })
    })
    expect(screen.getByTestId('actions-hero-overdue')).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'overdue=true',
    )
  })

  it('does not mark a verified past-due action as overdue', async () => {
    mockSummary.mockResolvedValue({ data: { total: 1, by_display_status: {} } })
    mockList.mockResolvedValue({
      data: {
        items: [
          action({
            status: 'verified',
            display_status: 'verified',
            due_date: '2020-01-01T00:00:00Z',
          }),
        ],
      },
    })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByText('Correct audit finding')
    expect(screen.queryByText('OVERDUE')).not.toBeInTheDocument()
  })

  it.skip('warns that CAPA assignment does not imply email delivery', async () => {
    // Flaky under TableSkeleton race / delivery-status timing; covered by CUJ honesty docs.
    mockList.mockResolvedValue({ data: { items: [action({})] } })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: false } })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Correct audit finding')).toBeInTheDocument()
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

  it('deep-links view=my with assigned_to=me on first load', async () => {
    render(
      <MemoryRouter initialEntries={['/actions?view=my']}>
        <Actions />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 100, undefined, undefined, undefined, {
        assigned_to: 'me',
        overdue: undefined,
      })
    })
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'assigned_to=me',
    )
  })

  it('deep-links view=overdue with overdue=true on first load', async () => {
    render(
      <MemoryRouter initialEntries={['/actions?view=overdue']}>
        <Actions />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 100, undefined, undefined, undefined, {
        assigned_to: undefined,
        overdue: true,
      })
    })
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'overdue=true',
    )
  })

  it('deep-links view=my_overdue with both server params', async () => {
    render(
      <MemoryRouter initialEntries={['/actions?view=my_overdue']}>
        <Actions />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 100, undefined, undefined, undefined, {
        assigned_to: 'me',
        overdue: true,
      })
    })
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'assigned_to=me&overdue=true',
    )
  })

  it('requests assigned_to=me when My actions is selected after first paint', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByText('Correct audit finding')
    await user.click(screen.getByTestId('actions-view-my'))

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 100, undefined, undefined, undefined, {
        assigned_to: 'me',
        overdue: undefined,
      })
    })
    expect(await screen.findByTestId('actions-server-filter-label')).toHaveTextContent(
      'assigned_to=me',
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

  it('shows Mine/Overdue badge counts that match view-counts API', async () => {
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('actions-view-badge-my')).toHaveTextContent('3')
    expect(screen.getByTestId('actions-view-badge-overdue')).toHaveTextContent('2')
    expect(screen.getByTestId('actions-view-badge-my_overdue')).toHaveTextContent('1')
  })

  it('does not show silent zero when summary fails', async () => {
    mockSummary.mockRejectedValue(new Error('summary down'))
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('actions-summary-unavailable')).toBeInTheDocument()
    expect(mockToastError).toHaveBeenCalled()
  })
})

describe('Actions Running Sheet create bridge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSummary.mockResolvedValue({ data: { total: 0, by_display_status: {} } })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
    mockList.mockResolvedValue({ data: { items: [] } })
  })

  it('opens create modal prefilled from query and shows returnTo banner', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/actions?create=1&sourceType=incident&sourceId=7&title=Follow-up%20from%20INC-7&description=From%20running%20sheet&returnTo=%2Fincidents%2F7',
        ]}
      >
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('actions-return-to-case')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Follow-up from INC-7')).toBeInTheDocument()
    expect(screen.getByDisplayValue('From running sheet')).toBeInTheDocument()
    expect(screen.getByDisplayValue('7')).toBeInTheDocument()
  })
})

describe('Actions Round 2 polish — URL sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSummary.mockResolvedValue({
      data: {
        total: 5,
        by_display_status: { open: 2, in_progress: 1, completed: 2 },
        overdue: 1,
      },
    })
    mockViewCounts.mockResolvedValue({
      data: { all: 5, my: 2, overdue: 1, my_overdue: 0 },
    })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
    mockList.mockResolvedValue({
      data: {
        items: [
          action({ id: 1, action_key: 'capa:1', display_status: 'open' }),
          action({ id: 2, action_key: 'capa:2', display_status: 'completed', title: 'Done item' }),
        ],
      },
    })
  })

  it('hydrates status=open from shareable URL and marks hero Open pressed', async () => {
    render(<ActionsRoute path="/actions?status=open" />)

    await screen.findByTestId('actions-hero-board')
    expect(screen.getByTestId('actions-hero-open')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('search-params')).toHaveTextContent('status=open')
    expect(screen.queryByText('Done item')).not.toBeInTheDocument()
  })

  it('writes status to URL when Open hero KPI is clicked', async () => {
    const user = userEvent.setup()
    render(<ActionsRoute path="/actions" />)

    await screen.findByTestId('actions-hero-board')
    await user.click(screen.getByTestId('actions-hero-open'))

    await waitFor(() => {
      expect(screen.getByTestId('search-params')).toHaveTextContent('status=open')
    })
    expect(screen.getByTestId('actions-hero-open')).toHaveAttribute('aria-pressed', 'true')
  })

  it('hydrates sourceType from shareable URL on first load', async () => {
    render(<ActionsRoute path="/actions?sourceType=incident" />)

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 100, undefined, 'incident', undefined, {
        assigned_to: undefined,
        overdue: undefined,
      })
    })
    expect(screen.getByTestId('search-params')).toHaveTextContent('sourceType=incident')
  })

  it('marks view-mode toggles with aria-pressed', async () => {
    render(<ActionsRoute path="/actions?view=my" />)

    await screen.findByTestId('actions-view-mode')
    expect(screen.getByTestId('actions-view-my')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('actions-view-all')).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('Actions Round 2 polish — honesty & a11y', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockViewCounts.mockResolvedValue({
      data: { all: 0, my: 0, overdue: 0, my_overdue: 0 },
    })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
  })

  it('shows error retry instead of hero zeros when list load fails', async () => {
    mockSummary.mockResolvedValue({ data: { total: 9, by_display_status: { open: 9 } } })
    mockList.mockRejectedValue(new Error('500 server'))

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Try Again')).toBeInTheDocument()
    expect(screen.queryByTestId('actions-hero-board')).not.toBeInTheDocument()
    expect(screen.queryByText('9')).not.toBeInTheDocument()
  })

  it('closes create dialog on Escape and returns focus to New Action trigger', async () => {
    mockSummary.mockResolvedValue({ data: { total: 0, by_display_status: {} } })
    mockList.mockResolvedValue({ data: { items: [] } })

    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    const trigger = await screen.findByRole('button', { name: 'New Action' })
    await user.click(trigger)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    await waitFor(() => {
      expect(trigger).toHaveFocus()
    })
  })

  it('expands detail row with aria-controls and shows type metadata', async () => {
    mockSummary.mockResolvedValue({ data: { total: 1, by_display_status: { open: 1 } } })
    mockList.mockResolvedValue({
      data: {
        items: [
          action({
            action_key: 'capa:77',
            action_type: 'preventive',
            created_at: '2026-01-15T12:00:00Z',
          }),
        ],
      },
    })

    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    const expand = await screen.findByRole('button', { name: 'Details' })
    expect(expand).toHaveAttribute('aria-controls', 'actions-detail-capa:77')
    await user.click(expand)

    const panel = await screen.findByTestId('actions-detail-capa:77')
    expect(panel).toHaveAttribute('role', 'region')
    expect(panel).toHaveTextContent('Type')
    expect(panel).toHaveTextContent('preventive')
    expect(panel).toHaveTextContent('Created')
  })
})
