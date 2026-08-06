import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Actions from '../Actions'

const mockList = vi.fn()
const mockSummary = vi.fn()
const mockViewCounts = vi.fn()
const mockGetDeliveryStatus = vi.fn()

const { tMock } = vi.hoisted(() => ({
  tMock: (key: string, fallback?: string) => fallback || key,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: tMock }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  actionsApi: {
    list: (...args: unknown[]) => mockList(...args),
    summary: (...args: unknown[]) => mockSummary(...args),
    viewCounts: (...args: unknown[]) => mockViewCounts(...args),
    create: vi.fn(),
  },
  investigationsApi: { createCapa: vi.fn() },
  notificationsApi: {
    getDeliveryStatus: (...args: unknown[]) => mockGetDeliveryStatus(...args),
  },
  getApiErrorMessage: () => 'An unexpected error occurred',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../utils/auth', () => ({
  getPlatformToken: () => 'fake.token',
  decodeTokenPayload: () => ({ sub: '42' }),
}))

/** A CAPA raised by a failed compliance check, as the unified API returns it. */
const complianceAction = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  reference_number: 'CAPA-2026-0009',
  title: 'Compliance Check Failed: Fire risk assessment — Wickford',
  description: 'Two fire doors failed inspection.',
  action_type: 'corrective',
  priority: 'critical',
  status: 'open',
  display_status: 'open',
  action_key: 'capa:1',
  source_type: 'compliance_record',
  // The occurrence, not the obligation — see capa_auto_service.
  source_id: 55,
  source_reference: 'compliance_requirement:10',
  owner_id: 7,
  created_at: '2026-06-01T09:00:00Z',
  ...overrides,
})

beforeAll(() => {
  // Radix Select uses pointer capture, which jsdom does not implement.
  const proto = Element.prototype as unknown as Record<string, unknown>
  proto.hasPointerCapture = () => false
  proto.setPointerCapture = () => {}
  proto.releasePointerCapture = () => {}
})

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  mockSummary.mockResolvedValue({ data: { total: 1, by_display_status: { open: 1 } } })
  mockViewCounts.mockResolvedValue({ data: { all: 1, my: 1, overdue: 0, my_overdue: 0 } })
  mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
  mockList.mockResolvedValue({ data: { items: [complianceAction()] } })
})

describe('compliance actions on the register', () => {
  it('links the row to its obligation, not to the occurrence id', async () => {
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    const link = await screen.findByRole('link', { name: 'View obligation' })
    expect(link).toHaveAttribute('href', '/compliance-schedule/10')
  })

  it('offers no obligation link when the row does not carry the requirement id', async () => {
    // Nothing writes this shape today, but /compliance-schedule/55 is a live
    // route: guessing from source_id would open a different obligation.
    mockList.mockResolvedValue({
      data: { items: [complianceAction({ source_reference: undefined })] },
    })

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await screen.findByText(/Compliance Check Failed/)
    expect(screen.queryByRole('link', { name: 'View obligation' })).not.toBeInTheDocument()
  })

  it('labels the source without printing the internal storage key', async () => {
    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Compliance record #55')).toBeInTheDocument()
    expect(screen.queryByText(/compliance_requirement:10/)).not.toBeInTheDocument()
  })

  it('passes the compliance source through to the server filter', async () => {
    render(
      <MemoryRouter initialEntries={['/actions?sourceType=compliance_record']}>
        <Actions />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(
        1,
        100,
        undefined,
        'compliance_record',
        undefined,
        expect.anything(),
      )
    })
  })
})

describe('compliance source filter option', () => {
  it('is offered when the Compliance Schedule module is on', async () => {
    window.localStorage.setItem('ff_override_compliance_schedule', 'true')
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await user.click(await screen.findByTestId('actions-source-filter'))
    expect(await screen.findByText('Compliance schedule')).toBeInTheDocument()
  })

  it('is withheld while the module is off, because it could only answer empty', async () => {
    window.localStorage.setItem('ff_override_compliance_schedule', 'false')
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Actions />
      </MemoryRouter>,
    )

    await user.click(await screen.findByTestId('actions-source-filter'))
    // Prove the menu really opened before trusting the absence.
    expect(await screen.findByText('Regulatory watch')).toBeInTheDocument()
    expect(screen.queryByText('Compliance schedule')).not.toBeInTheDocument()
  })

  it('still names the filter on the trigger when a deep link selected it with the module off', async () => {
    // Radix reads the trigger label off the matching item, so withholding the
    // item unconditionally would leave a filtered register above a blank filter.
    window.localStorage.setItem('ff_override_compliance_schedule', 'false')

    render(
      <MemoryRouter initialEntries={['/actions?sourceType=compliance_record']}>
        <Actions />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('actions-source-filter')).toHaveTextContent(
      'Compliance schedule',
    )
  })
})
