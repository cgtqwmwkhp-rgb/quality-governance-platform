/**
 * Regression cover for the New RTA modal defects: PX-203 (required fields not
 * marked anywhere) and PX-204 (a submit that gives no feedback, inviting a
 * second click and a duplicate record on a register with no delete path).
 */
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import RTAs from '../RTAs'

beforeAll(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const proto = Element.prototype as any
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false
  if (!proto.setPointerCapture) proto.setPointerCapture = () => undefined
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => undefined
  if (!proto.scrollIntoView) proto.scrollIntoView = () => undefined
  // Radix Switch measures its thumb via ResizeObserver, absent from jsdom.
  if (!('ResizeObserver' in globalThis)) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(globalThis as any).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: unknown) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const mockList = vi.fn()
const mockCreate = vi.fn()

vi.mock('../../api/client', () => ({
  rtasApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../utils/errorTracker', () => ({ trackError: vi.fn() }))

vi.mock('../../utils/platformSessionReporter', () => ({
  resolvePlatformReporterIdentity: vi.fn().mockResolvedValue({
    reporter_name: 'Alex Controller',
    reporter_email: 'alex@example.com',
  }),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

/** Every required control in the New RTA modal, by DOM id. */
const REQUIRED_CONTROL_IDS = ['rtas-field-0', 'rtas-field-1', 'rtas-field-2', 'rtas-field-6']
const OPTIONAL_CONTROL_IDS = ['rtas-field-4', 'rtas-field-5', 'rtas-field-reporter']

async function openCreateModal() {
  const user = userEvent.setup()
  render(<RTAs />, { wrapper: Wrapper })
  await waitFor(() => expect(screen.getByTestId('create-rta-btn')).toBeInTheDocument())
  await user.click(screen.getByTestId('create-rta-btn'))
  await screen.findByText('rtas.dialog.title')
  return user
}

describe('New RTA modal — shared form primitive', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { items: [], total: 0 } })
    mockCreate.mockResolvedValue({ data: { id: 1 } })
  })

  it('PX-203: every required field is marked visually and programmatically', async () => {
    await openCreateModal()

    for (const id of REQUIRED_CONTROL_IDS) {
      const control = document.getElementById(id)
      expect(control, `control ${id} should exist`).toBeTruthy()
      expect(control).toHaveAttribute('aria-required', 'true')

      const label = document.querySelector(`label[for="${id}"]`)
      expect(label, `label for ${id} should exist`).toBeTruthy()
      // The asterisk and aria-required come from the same prop, so a field can
      // never again be programmatically required but visually unmarked.
      expect(label?.textContent).toContain('*')
    }
  })

  it('PX-203: optional fields are not falsely marked', async () => {
    await openCreateModal()

    for (const id of OPTIONAL_CONTROL_IDS) {
      const control = document.getElementById(id)
      expect(control).toBeTruthy()
      expect(control).not.toHaveAttribute('aria-required')
      expect(document.querySelector(`label[for="${id}"]`)?.textContent).not.toContain('*')
    }
  })

  it('PX-204: submit is disabled and shows progress while the request is in flight', async () => {
    let release: () => void = () => {}
    mockCreate.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ data: { id: 1 } })
        }),
    )

    const user = await openCreateModal()
    await user.type(screen.getByPlaceholderText('rtas.form.placeholder.title'), 'Rear-end on A38')
    await user.type(
      screen.getByPlaceholderText('rtas.form.placeholder.description'),
      'Low speed contact',
    )
    await user.type(screen.getByPlaceholderText('rtas.form.placeholder.location'), 'A38 southbound')

    await user.click(screen.getByTestId('rta-create-submit'))

    await waitFor(() => expect(screen.getByTestId('rta-create-submit')).toBeDisabled())
    expect(screen.getByTestId('rta-create-submit')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByTestId('rta-create-submit')).toHaveTextContent('rtas.reporting')
    // Progress is also announced, not just drawn.
    expect(screen.getByRole('status')).toHaveTextContent('rtas.reporting')

    release()
    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
  })

  it('PX-204: a second click while in flight cannot create a duplicate record', async () => {
    let release: () => void = () => {}
    mockCreate.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ data: { id: 1 } })
        }),
    )

    const user = await openCreateModal()
    await user.type(screen.getByPlaceholderText('rtas.form.placeholder.title'), 'Rear-end on A38')
    await user.type(
      screen.getByPlaceholderText('rtas.form.placeholder.description'),
      'Low speed contact',
    )
    await user.type(screen.getByPlaceholderText('rtas.form.placeholder.location'), 'A38 southbound')

    const submit = screen.getByTestId('rta-create-submit')
    await user.click(submit)
    await waitFor(() => expect(submit).toBeDisabled())
    await user.click(submit)
    await user.click(submit)

    expect(mockCreate).toHaveBeenCalledTimes(1)
    release()
  })

  it('PX-291-class: an incomplete RTA is refused with a named, field-adjacent error', async () => {
    const user = await openCreateModal()

    await user.click(screen.getByTestId('rta-create-submit'))

    expect(mockCreate).not.toHaveBeenCalled()
    const error = await screen.findByTestId('rtas-field-0-error')
    expect(error).toHaveTextContent('common.title is required')
    expect(document.activeElement).toBe(document.getElementById('rtas-field-0'))
  })

  it('PX-208-class: a failed create leaves a persistent error, not a toast', async () => {
    mockCreate.mockRejectedValue(new Error('Service unavailable'))

    const user = await openCreateModal()
    await user.type(screen.getByPlaceholderText('rtas.form.placeholder.title'), 'Rear-end on A38')
    await user.type(
      screen.getByPlaceholderText('rtas.form.placeholder.description'),
      'Low speed contact',
    )
    await user.type(screen.getByPlaceholderText('rtas.form.placeholder.location'), 'A38 southbound')
    await user.click(screen.getByTestId('rta-create-submit'))

    expect(await screen.findByTestId('rta-create-error')).toHaveTextContent('Service unavailable')
    await new Promise((resolve) => setTimeout(resolve, 60))
    expect(screen.getByTestId('rta-create-error')).toHaveTextContent('Service unavailable')
  })
})
