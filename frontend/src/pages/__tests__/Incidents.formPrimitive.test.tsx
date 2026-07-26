/**
 * Regression cover for the New Incident modal defects fixed by the shared form
 * primitive: PX-291 (silent required-field failure) and PX-127 (an offline save
 * that looked exactly like a successful one).
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Incidents from '../Incidents'

beforeAll(() => {
  // Radix Select requires PointerEvent capture APIs missing from jsdom.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const proto = Element.prototype as any
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false
  if (!proto.setPointerCapture) proto.setPointerCapture = () => undefined
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => undefined
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => undefined
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    // Fall through to the in-code English default so assertions read naturally.
    t: (key: string, fallback?: unknown) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const mockList = vi.fn()
const mockCreate = vi.fn()

vi.mock('../../api/client', () => ({
  incidentsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
  lookupsApi: {
    list: vi.fn().mockImplementation(async (category: string) => {
      if (category === 'customers') {
        return {
          items: [
            { id: 10, category: 'customers', code: 'acme', label: 'Acme Corp', is_active: true },
          ],
          total: 1,
        }
      }
      return { items: [], total: 0 }
    }),
  },
  contractsApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: 1, code: 'acme', name: 'Acme Corp', is_active: true }],
      total: 1,
    }),
  },
  notificationsApi: {
    getDeliveryStatus: vi.fn().mockResolvedValue({ data: { email_configured: true } }),
  },
  workforceApi: { listEngineers: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }) },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../components/EngineerPeoplePicker', () => ({
  EngineerPeoplePicker: () => <input data-testid="engineer-people-picker" />,
}))

vi.mock('../../utils/errorTracker', () => ({ trackError: vi.fn() }))

vi.mock('../../utils/platformSessionReporter', () => ({
  resolvePlatformReporterIdentity: vi
    .fn()
    .mockResolvedValue({ reporter_name: 'Alex', reporter_email: 'alex@example.com' }),
}))

const mockQueueForSync = vi.fn()
vi.mock('../../lib/syncService', () => ({
  queueForSync: (...args: unknown[]) => mockQueueForSync(...args),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

const emptyList = {
  data: { items: [], total: 0, page: 1, page_size: 50, total_pages: 1 },
}

async function openCreateModal() {
  const user = userEvent.setup()
  render(<Incidents />, { wrapper: Wrapper })
  await waitFor(() => expect(screen.getByText('incidents.new')).toBeInTheDocument())
  await user.click(screen.getByText('incidents.new'))
  await screen.findByText('incidents.dialog.title')
  return user
}

async function fillEverythingExceptCustomer(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByPlaceholderText('incidents.form.title_placeholder'),
    'Forklift near miss',
  )
  await user.type(
    screen.getByPlaceholderText('incidents.form.description_placeholder'),
    'Pedestrian walked into the aisle',
  )
}

describe('New Incident modal — shared form primitive', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue(emptyList)
    mockCreate.mockResolvedValue({ data: { id: 3, reference_number: 'INC-003' } })
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
  })

  afterEach(() => {
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
  })

  it('PX-291: names the missing required field instead of failing silently', async () => {
    const user = await openCreateModal()
    await fillEverythingExceptCustomer(user)

    await user.click(screen.getByText('incidents.create'))

    // No request went out...
    expect(mockCreate).not.toHaveBeenCalled()

    // ...and the user is told exactly which field, next to that field.
    const error = await screen.findByTestId('incidents-field-customer-error')
    expect(error).toHaveTextContent(/Customer \/ contract is required/)
    expect(error).toHaveAttribute('role', 'alert')
  })

  it('PX-291: marks the offending control invalid and moves focus to it', async () => {
    const user = await openCreateModal()
    await fillEverythingExceptCustomer(user)
    await user.click(screen.getByText('incidents.create'))

    const trigger = await waitFor(() => {
      const el = document.getElementById('incidents-field-customer')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(trigger).toHaveAttribute('aria-invalid', 'true')
    expect(trigger).toHaveAttribute('aria-required', 'true')
    expect(document.activeElement).toBe(trigger)
  })

  it('PX-203-class: required fields carry both an asterisk and aria-required', async () => {
    await openCreateModal()

    const title = screen.getByPlaceholderText('incidents.form.title_placeholder')
    expect(title).toBeRequired()
    expect(title).toHaveAttribute('aria-required', 'true')

    const customerLabel = document.querySelector('label[for="incidents-field-customer"]')
    expect(customerLabel?.textContent).toContain('*')
  })

  it('PX-291: the error clears once the user supplies the value, and submit goes through', async () => {
    const user = await openCreateModal()
    await fillEverythingExceptCustomer(user)
    await user.click(screen.getByText('incidents.create'))
    await screen.findByTestId('incidents-field-customer-error')

    await user.click(document.getElementById('incidents-field-customer') as HTMLElement)
    await user.click(await screen.findByRole('option', { name: 'Acme Corp' }))

    await waitFor(() =>
      expect(screen.queryByTestId('incidents-field-customer-error')).not.toBeInTheDocument(),
    )

    await user.click(screen.getByText('incidents.create'))
    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
  })

  it('PX-127: an offline save says so and does not close as if it had succeeded', async () => {
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false })
    mockQueueForSync.mockResolvedValue(undefined)

    const user = await openCreateModal()
    await fillEverythingExceptCustomer(user)
    await user.click(document.getElementById('incidents-field-customer') as HTMLElement)
    await user.click(await screen.findByRole('option', { name: 'Acme Corp' }))
    await user.click(screen.getByText('incidents.create'))

    await waitFor(() => expect(mockQueueForSync).toHaveBeenCalledTimes(1))
    expect(mockCreate).not.toHaveBeenCalled()

    const notice = await screen.findByTestId('incident-offline-queued')
    expect(notice).toHaveTextContent(/Saved offline/i)
    expect(notice).toHaveTextContent(/will not appear in the register/i)

    // The dialog is still open — an offline save must not look like a success.
    expect(screen.getByText('incidents.dialog.title')).toBeInTheDocument()
  })

  it('PX-172: Escape on a dirty form asks before throwing the work away', async () => {
    const user = await openCreateModal()
    await fillEverythingExceptCustomer(user)

    await user.keyboard('{Escape}')

    expect(await screen.findByTestId('incident-unsaved-changes')).toBeInTheDocument()
    expect(screen.getByText('incidents.dialog.title')).toBeInTheDocument()

    await user.click(screen.getByTestId('incident-unsaved-changes-keep'))
    await waitFor(() =>
      expect(screen.queryByTestId('incident-unsaved-changes')).not.toBeInTheDocument(),
    )
    expect(screen.getByPlaceholderText('incidents.form.title_placeholder')).toHaveValue(
      'Forklift near miss',
    )
  })

  it('PX-172: Escape on an untouched form still closes immediately', async () => {
    const user = await openCreateModal()

    await user.keyboard('{Escape}')

    await waitFor(() =>
      expect(screen.queryByText('incidents.dialog.title')).not.toBeInTheDocument(),
    )
    expect(screen.queryByTestId('incident-unsaved-changes')).not.toBeInTheDocument()
  })

  it('PX-208-class: a failed create leaves a persistent error in the dialog', async () => {
    mockCreate.mockRejectedValue(new Error('Gateway timeout'))

    const user = await openCreateModal()
    await fillEverythingExceptCustomer(user)
    await user.click(document.getElementById('incidents-field-customer') as HTMLElement)
    await user.click(await screen.findByRole('option', { name: 'Acme Corp' }))
    await user.click(screen.getByText('incidents.create'))

    const notice = await screen.findByTestId('incident-create-error')
    expect(notice).toHaveTextContent('Gateway timeout')

    // Long after any toast would have gone.
    await new Promise((resolve) => setTimeout(resolve, 60))
    expect(screen.getByTestId('incident-create-error')).toHaveTextContent('Gateway timeout')
  })
})
